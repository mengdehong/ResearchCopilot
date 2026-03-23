"""Extraction WF 全链路测试。

编译完整的 extraction 子图，端到端验证：
  wait_rag_ready → check_existing_notes → retrieve_chunks → generate_notes
  → cross_compare → build_glossary → write_artifacts

RAGEngine 和 LLM 使用 mock，但通过真实的 LangGraph 图执行，
验证节点间 state 传递（retrieve_chunks 输出 → generate_notes 输入）完整贯通。
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agent.state import ComparisonEntry
from backend.agent.workflows.extraction.graph import build_extraction_graph
from backend.agent.workflows.extraction.nodes import (
    ComparisonResult,
    GeneratedNote,
    GlossaryResult,
)
from backend.services.rag_engine import RetrievedChunk


def _build_mock_llm() -> MagicMock:
    """构建 mock LLM，按节点调用顺序返回结构化输出。

    调用顺序：generate_notes → cross_compare → build_glossary
    """
    responses = [
        # generate_notes: paper p1
        GeneratedNote(
            key_contributions=["contribution from full text"],
            methodology="method from chunks",
            experimental_setup="setup1",
            main_results="result1",
            limitations=["lim1"],
        ),
        # generate_notes: paper p2
        GeneratedNote(
            key_contributions=["contribution2"],
            methodology="method2",
            experimental_setup="setup2",
            main_results="result2",
            limitations=["lim2"],
        ),
        # cross_compare
        ComparisonResult(
            entries=[
                ComparisonEntry(
                    paper_id="p1",
                    method="m",
                    dataset="d",
                    metric_values={"acc": 0.9},
                    key_difference="diff",
                ),
            ]
        ),
        # build_glossary
        GlossaryResult(terms={"RAG": "Retrieval-Augmented Generation"}),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _build_mock_rag_engine() -> MagicMock:
    """构建 mock RAGEngine，为两篇论文各返回不同的 chunks。"""
    doc_uuid_1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    doc_uuid_2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

    chunks_map = {
        doc_uuid_1: [
            RetrievedChunk(
                chunk_id=uuid.uuid4(),
                document_id=doc_uuid_1,
                content_text="We propose a novel method for...",
                content_type="paragraph",
                section_path="Introduction",
                page_numbers=[1, 2],
                score=0.95,
            ),
            RetrievedChunk(
                chunk_id=uuid.uuid4(),
                document_id=doc_uuid_1,
                content_text="Experimental results show that...",
                content_type="paragraph",
                section_path="Results",
                page_numbers=[5],
                score=0.88,
            ),
        ],
        doc_uuid_2: [
            RetrievedChunk(
                chunk_id=uuid.uuid4(),
                document_id=doc_uuid_2,
                content_text="Our approach differs from prior work...",
                content_type="paragraph",
                section_path="Related Work",
                page_numbers=[3],
                score=0.82,
            ),
        ],
    }

    async def _mock_retrieve(query, session):
        doc_ids = query.document_ids or []
        result = []
        for doc_id in doc_ids:
            result.extend(chunks_map.get(doc_id, []))
        return result

    rag_engine = MagicMock()
    rag_engine.retrieve = AsyncMock(side_effect=_mock_retrieve)
    return rag_engine


@pytest.mark.asyncio
async def test_extraction_chain_retrieve_to_notes() -> None:
    """全链路：Discovery artifacts → retrieve_chunks → generate_notes → artifacts。

    验证：
    1. retrieve_chunks 正确映射 arxiv_id → document_id 并调用 RAGEngine
    2. generate_notes 收到 retrieved_chunks 并填充 source_chunks
    3. 最终 artifacts 包含完整的 reading_notes + comparison + glossary
    """
    workspace_id = str(uuid.uuid4())
    doc_uuid_1 = "11111111-1111-1111-1111-111111111111"
    doc_uuid_2 = "22222222-2222-2222-2222-222222222222"

    llm = _build_mock_llm()
    rag_engine = _build_mock_rag_engine()

    mock_session = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    # 编译完整子图
    graph = build_extraction_graph(llm=llm, rag_engine=rag_engine, session_factory=session_factory)
    compiled = graph.compile()

    # Discovery 阶段产出的 artifacts（模拟上游输入）
    input_state = {
        "messages": [],
        "workspace_id": workspace_id,
        "discipline": "cs",
        "artifacts": {
            "discovery": {
                "selected_paper_ids": ["p1", "p2"],
                "ingestion_task_ids": [doc_uuid_1, doc_uuid_2],
                "papers": [
                    {"arxiv_id": "p1", "title": "Paper One", "abstract": "Abstract of paper one"},
                    {"arxiv_id": "p2", "title": "Paper Two", "abstract": "Abstract of paper two"},
                ],
            },
        },
    }

    result = await compiled.ainvoke(input_state)

    # ── 验证 RAGEngine 被正确调用 ──
    assert rag_engine.retrieve.call_count == 2

    # ── 验证 artifacts 输出 ──
    extraction_artifacts = result["artifacts"]["extraction"]

    # reading_notes: 两篇论文各一个
    notes = extraction_artifacts["reading_notes"]
    assert len(notes) == 2

    note_1 = notes[0]
    note_2 = notes[1]
    assert note_1["paper_id"] == "p1"
    assert note_2["paper_id"] == "p2"

    # source_chunks 被正确填充（p1 有 2 个 chunk, p2 有 1 个）
    assert len(note_1["source_chunks"]) == 2, (
        f"p1 should have 2 source_chunks, got {len(note_1['source_chunks'])}"
    )
    assert len(note_2["source_chunks"]) == 1, (
        f"p2 should have 1 source_chunk, got {len(note_2['source_chunks'])}"
    )

    # comparison_matrix 非空
    assert len(extraction_artifacts["comparison_matrix"]) >= 1

    # glossary 被填充
    assert "RAG" in extraction_artifacts["glossary"]


@pytest.mark.asyncio
async def test_extraction_chain_no_ingestion_graceful() -> None:
    """链路降级：无 ingestion_task_ids 时，retrieve_chunks 返回空，generate_notes 仍能基于 abstract 跑通。"""
    workspace_id = str(uuid.uuid4())

    responses = [
        GeneratedNote(
            key_contributions=["c1"],
            methodology="m1",
            experimental_setup="s1",
            main_results="r1",
            limitations=["l1"],
        ),
        GlossaryResult(terms={"term": "def"}),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)

    rag_engine = MagicMock()
    rag_engine.retrieve = AsyncMock(return_value=[])

    mock_session = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    graph = build_extraction_graph(llm=llm, rag_engine=rag_engine, session_factory=session_factory)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": workspace_id,
        "discipline": "cs",
        "artifacts": {
            "discovery": {
                "selected_paper_ids": ["p1"],
                "ingestion_task_ids": [],  # 空！没有 ingestion
                "papers": [
                    {"arxiv_id": "p1", "title": "Paper", "abstract": "Abstract"},
                ],
            },
        },
    }

    result = await compiled.ainvoke(input_state)

    # retrieve 未被调用（无 doc mapping）
    rag_engine.retrieve.assert_not_called()

    # 但 notes 仍然生成了（基于 abstract）
    notes = result["artifacts"]["extraction"]["reading_notes"]
    assert len(notes) == 1
    assert notes[0]["source_chunks"] == []  # 无 chunks
