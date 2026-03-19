"""RAG Engine 单元测试。"""

import uuid

from backend.services.rag_engine import RAGEngine, RetrievedChunk


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
