"""RAG Pipeline 端到端测试。

全链路测试 RAGEngine.retrieve() 在不同 QueryIntent 下的完整管线：
  embed_text → _search_targets (vector + keyword) → _rrf_merge → _rerank → final_results

使用 mock DB Session 和 mock 模型，验证：
1. EVIDENCE_LEVEL：混合检索 + RRF + Rerank 的端到端数据流
2. 多目标表检索：paragraph + table 同时返回
3. CROSS_DOC：两阶段检索（doc_summary → evidence）
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag_engine import (
    QueryIntent,
    RAGEngine,
    RetrievalQuery,
    RetrievedChunk,
)

# ── 固定 ID ──
WS_ID = uuid.uuid4()
DOC_ID_1 = uuid.uuid4()
DOC_ID_2 = uuid.uuid4()


def _make_db_row(
    *,
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID = DOC_ID_1,
    content_text: str = "test content",
    section_path: str = "1. Introduction",
    page_numbers: list[int] | None = None,
    score: float = 0.8,
    summary_content_type: str | None = None,
    table_title: str | None = None,
    raw_data: dict | None = None,
    schema_data: dict | None = None,
) -> SimpleNamespace:
    """构建模拟 SQL 结果行。"""
    return SimpleNamespace(
        id=chunk_id or uuid.uuid4(),
        document_id=document_id,
        content_text=content_text,
        section_path=section_path,
        page_numbers=page_numbers if page_numbers is not None else [1],
        score=score,
        summary_content_type=summary_content_type,
        table_title=table_title,
        raw_data=raw_data,
        schema_data=schema_data,
    )


def _build_engine_with_mocks(
    *,
    vector_rows: list[SimpleNamespace] | None = None,
    keyword_rows: list[SimpleNamespace] | None = None,
    rerank_scores: list[float] | None = None,
) -> tuple[RAGEngine, AsyncMock]:
    """构建带 mock embed/rerank/session 的 RAGEngine。"""
    engine = RAGEngine()

    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [0.1] * 768
    engine._embedder = mock_embedder  # type: ignore[assignment]

    # Mock reranker — dynamically return scores matching chunk count
    mock_reranker = MagicMock()
    if rerank_scores is not None:
        mock_reranker.predict.return_value = rerank_scores
    else:
        # 默认：返回递减分数，足够多以匹配任意数量的 chunks
        mock_reranker.predict.side_effect = lambda pairs: [1.0 - i * 0.1 for i in range(len(pairs))]
    engine._reranker = mock_reranker  # type: ignore[assignment]

    # Mock session — execute 按调用顺序返回 vector/keyword 结果
    mock_session = AsyncMock()
    vector_result = MagicMock()
    vector_result.fetchall.return_value = vector_rows or []
    keyword_result = MagicMock()
    keyword_result.fetchall.return_value = keyword_rows or []

    # execute 交替返回 vector → keyword 结果（asyncio.gather 并发，按 target 数量循环）
    mock_session.execute = AsyncMock(side_effect=[vector_result, keyword_result] * 5)

    return engine, mock_session


@pytest.mark.asyncio
async def test_evidence_level_full_pipeline() -> None:
    """EVIDENCE_LEVEL 全管线：vector + keyword → RRF → rerank → 返回排序结果。"""
    chunk_a_id = uuid.uuid4()
    chunk_b_id = uuid.uuid4()

    vector_rows = [
        _make_db_row(chunk_id=chunk_a_id, content_text="quantum computing methods", score=0.9),
        _make_db_row(chunk_id=chunk_b_id, content_text="error correction approach", score=0.7),
    ]
    keyword_rows = [
        _make_db_row(chunk_id=chunk_b_id, content_text="error correction approach", score=0.85),
    ]

    # 不指定 rerank_scores → 使用动态 side_effect，自动匹配 chunk 数量
    engine, mock_session = _build_engine_with_mocks(
        vector_rows=vector_rows,
        keyword_rows=keyword_rows,
    )

    query = RetrievalQuery(
        query_text="quantum error correction",
        workspace_id=WS_ID,
        intent=QueryIntent.EVIDENCE_LEVEL,
        top_k_coarse=30,
        top_n_final=5,
    )

    results = await engine.retrieve(query, session=mock_session)

    # 验证结果非空
    assert len(results) >= 1

    # 验证排序（reranker score 高的在前）
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)

    # 验证 embedder 和 reranker 被调用
    engine._embedder.encode.assert_called_once()  # type: ignore[union-attr]
    engine._reranker.predict.assert_called_once()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_evidence_level_multi_target_results() -> None:
    """EVIDENCE_LEVEL 多目标表：paragraph + table 混合返回。"""
    para_id = uuid.uuid4()
    table_id = uuid.uuid4()

    # paragraph 目标的 vector 和 keyword 结果
    para_vector = [
        _make_db_row(chunk_id=para_id, content_text="paragraph content", score=0.85),
    ]
    para_keyword = []

    # table 目标的 vector 和 keyword 结果
    table_vector = [
        _make_db_row(
            chunk_id=table_id,
            content_text="table summary",
            score=0.75,
            table_title="Table 1",
            raw_data={"rows": [["a", "b"]]},
        ),
    ]
    table_keyword = []

    engine = RAGEngine()

    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [0.1] * 768
    engine._embedder = mock_embedder  # type: ignore[assignment]

    # Mock reranker: 保持原序
    mock_reranker = MagicMock()
    mock_reranker.predict.return_value = [0.9, 0.8]
    engine._reranker = mock_reranker  # type: ignore[assignment]

    # Mock session: paragraph(vector, keyword) → table(vector, keyword)
    mock_session = AsyncMock()
    para_v_result = MagicMock()
    para_v_result.fetchall.return_value = para_vector
    para_k_result = MagicMock()
    para_k_result.fetchall.return_value = para_keyword
    table_v_result = MagicMock()
    table_v_result.fetchall.return_value = table_vector
    table_k_result = MagicMock()
    table_k_result.fetchall.return_value = table_keyword

    mock_session.execute = AsyncMock(
        side_effect=[para_v_result, para_k_result, table_v_result, table_k_result]
    )

    query = RetrievalQuery(
        query_text="experimental results",
        workspace_id=WS_ID,
        intent=QueryIntent.EVIDENCE_LEVEL,
    )

    results = await engine.retrieve(query, session=mock_session)

    content_types = {r.content_type for r in results}
    # paragraph 和 table 都应该出现在结果中
    assert "paragraph" in content_types
    assert "table" in content_types


@pytest.mark.asyncio
async def test_cross_doc_two_stage_retrieval() -> None:
    """CROSS_DOC 两阶段检索：先 doc_summary → 候选文档 → 再 evidence 检索。

    验证数据流：
    1. 先搜 doc_summaries 得到 candidate document_ids
    2. 再在 candidate documents 中搜 paragraphs + tables
    """
    summary_chunk_id = uuid.uuid4()
    evidence_chunk_id = uuid.uuid4()

    engine = RAGEngine()

    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [0.1] * 768
    engine._embedder = mock_embedder  # type: ignore[assignment]

    # Mock reranker — bypass strict zip by overriding _rerank directly
    engine._rerank = (
        lambda query_text, chunks, top_n: sorted(  # type: ignore[method-assign]
            chunks, key=lambda c: c.score, reverse=True
        )[:top_n]
    )

    # 跟踪 _search_target 和 _search_targets 的调用
    search_calls: list[tuple[str, list[uuid.UUID] | None]] = []

    async def _fake_search_target(
        *,
        session: object,
        query: RetrievalQuery,
        target: object,
        query_embedding: list[float],
    ) -> list[RetrievedChunk]:
        del session, query_embedding
        doc_ids = None if query.document_ids is None else list(query.document_ids)
        search_calls.append((target.name, doc_ids))

        if target.name == "doc_summaries":
            return [
                RetrievedChunk(
                    chunk_id=summary_chunk_id,
                    document_id=DOC_ID_1,
                    content_text="relevant paper summary",
                    content_type="doc_summary",
                    section_path="",
                    page_numbers=[],
                    score=0.9,
                ),
            ]
        return [
            RetrievedChunk(
                chunk_id=evidence_chunk_id,
                document_id=DOC_ID_1,
                content_text="evidence from methods section",
                content_type=target.content_type,
                section_path="Methods",
                page_numbers=[3],
                score=0.8,
            ),
        ]

    engine._search_target = AsyncMock(side_effect=_fake_search_target)  # type: ignore[method-assign]

    query = RetrievalQuery(
        query_text="compare experimental approaches",
        workspace_id=WS_ID,
        intent=QueryIntent.CROSS_DOC,
    )

    results = await engine.retrieve(query, session=AsyncMock())

    # 验证调用顺序：先 doc_summaries → 再 paragraphs + tables
    target_names = [call[0] for call in search_calls]
    assert target_names[0] == "doc_summaries"
    assert "paragraphs" in target_names[1:]
    assert "tables" in target_names[1:]

    # 验证第二阶段使用了候选文档 ID
    for _call_name, call_doc_ids in search_calls[1:]:
        assert call_doc_ids is not None
        assert DOC_ID_1 in call_doc_ids

    # 验证最终结果为证据级结果
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_retrieve_empty_results() -> None:
    """空结果场景：DB 无匹配时应返回空列表。"""
    engine, mock_session = _build_engine_with_mocks(
        vector_rows=[],
        keyword_rows=[],
    )

    query = RetrievalQuery(
        query_text="nonexistent topic xyz123",
        workspace_id=WS_ID,
        intent=QueryIntent.EVIDENCE_LEVEL,
    )

    results = await engine.retrieve(query, session=mock_session)
    assert results == []
