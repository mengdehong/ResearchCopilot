"""RAG Engine 单元测试。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.rag_engine import (
    QueryIntent,
    RAGEngine,
    RetrievalQuery,
    RetrievedChunk,
)


def _make_chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.UUID(chunk_id),
        document_id=uuid.uuid4(),
        content_text="test",
        content_type="paragraph",
        section_path="1. Intro",
        page_numbers=[1],
        score=score,
    )


ID_A = "00000000-0000-0000-0000-000000000001"
ID_B = "00000000-0000-0000-0000-000000000002"
ID_C = "00000000-0000-0000-0000-000000000003"


def test_rrf_merge_basic() -> None:
    """B 出现在两个列表中, RRF 分数应最高。"""
    list_a = [_make_chunk(ID_A, 0.9), _make_chunk(ID_B, 0.8)]
    list_b = [_make_chunk(ID_B, 0.85), _make_chunk(ID_C, 0.7)]

    merged = RAGEngine._rrf_merge(list_a, list_b)
    ids = [str(c.chunk_id) for c in merged]

    # B 出现在两个列表中, RRF 分数应最高
    assert ids[0] == ID_B
    assert len(merged) == 3


def test_rrf_merge_empty() -> None:
    """空列表合并应返回空列表。"""
    merged = RAGEngine._rrf_merge([], [])
    assert merged == []


def test_get_retrieval_targets_document_level() -> None:
    """document_level 只检索 doc_summaries。"""
    engine = RAGEngine()

    targets = engine._get_retrieval_targets(QueryIntent.DOCUMENT_LEVEL)

    assert [target.name for target in targets] == ["doc_summaries"]


def test_get_retrieval_targets_evidence_level() -> None:
    """evidence_level 检索 paragraphs 和 tables。"""
    engine = RAGEngine()

    targets = engine._get_retrieval_targets(QueryIntent.EVIDENCE_LEVEL)

    assert [target.name for target in targets] == ["paragraphs", "tables"]


@pytest.mark.asyncio
async def test_retrieve_cross_doc_uses_doc_summary_candidates_before_evidence() -> None:
    """cross_doc 先查 doc_summaries, 再用候选文档过滤证据表。"""
    workspace_id = uuid.uuid4()
    candidate_document_id = uuid.uuid4()
    query = RetrievalQuery(
        query_text="compare methods",
        workspace_id=workspace_id,
        intent=QueryIntent.CROSS_DOC,
    )
    engine = RAGEngine()
    call_sequence: list[tuple[str, list[uuid.UUID] | None]] = []

    async def fake_search_target(
        *,
        session: object,
        query: RetrievalQuery,
        target: object,
        query_embedding: list[float],
    ) -> list[RetrievedChunk]:
        del session, query_embedding
        document_ids = None if query.document_ids is None else list(query.document_ids)
        call_sequence.append((target.name, document_ids))
        if target.name == "doc_summaries":
            return [
                RetrievedChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=candidate_document_id,
                    content_text="summary",
                    content_type="doc_summary",
                    section_path="",
                    page_numbers=[],
                    score=0.9,
                )
            ]
        return [
            RetrievedChunk(
                chunk_id=uuid.uuid4(),
                document_id=candidate_document_id,
                content_text=target.name,
                content_type=target.content_type,
                section_path="Methods",
                page_numbers=[1],
                score=0.7,
            )
        ]

    engine.embed_text = lambda text_input: [0.1, 0.2]  # type: ignore[method-assign]
    engine._search_target = AsyncMock(side_effect=fake_search_target)  # type: ignore[method-assign]
    engine._rerank = lambda query_text, chunks, top_n: list(chunks)[:top_n]  # type: ignore[method-assign]

    results = await engine.retrieve(query, session=object())  # type: ignore[arg-type]

    assert [item[0] for item in call_sequence] == ["doc_summaries", "paragraphs", "tables"]
    assert call_sequence[1][1] == [candidate_document_id]
    assert call_sequence[2][1] == [candidate_document_id]
    assert [chunk.content_type for chunk in results] == ["paragraph", "table"]


def test_rerank_resorts_rrf_results() -> None:
    """reranker 分数应覆盖 RRF 原顺序。"""
    engine = RAGEngine()
    chunks = [
        _make_chunk(ID_A, 1.0),
        _make_chunk(ID_B, 0.9),
    ]

    class FakeReranker:
        def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
            assert pairs == [
                ("query", "test"),
                ("query", "test"),
            ]
            return [0.1, 0.95]

    engine._reranker = FakeReranker()  # type: ignore[attr-defined]
    reranked = engine._rerank("query", chunks, top_n=2)

    assert [str(chunk.chunk_id) for chunk in reranked] == [ID_B, ID_A]
    assert reranked[0].score == pytest.approx(0.95)


def test_map_table_row_to_chunk_includes_raw_data() -> None:
    """table 结果应映射 raw_data 和页码。"""
    engine = RAGEngine()
    row = SimpleNamespace(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content_text="table summary",
        section_path="Results",
        page_numbers=[4],
        score=0.8,
        table_title="Table 1",
        raw_data={"rows": [["a", "b"]]},
        schema_data={"best_metric": "acc"},
        summary_content_type=None,
    )
    target = engine._get_retrieval_targets(QueryIntent.EVIDENCE_LEVEL)[1]

    chunk = engine._map_row_to_chunk(row=row, target=target)

    assert chunk.content_type == "table"
    assert chunk.page_numbers == [4]
    assert chunk.metadata["raw_data"] == {"rows": [["a", "b"]]}
    assert chunk.metadata["table_title"] == "Table 1"
