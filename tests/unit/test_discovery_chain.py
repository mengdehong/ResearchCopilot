"""Discovery WF 全链路测试。

编译完整的 Discovery 子图，端到端验证：
  expand_query → search_apis → filter_and_rank → present_candidates (HITL)
  → trigger_ingestion → wait_for_ingestion → write_artifacts

LLM / ArXiv API / httpx / interrupt 使用 mock，但通过真实 LangGraph 图执行，
验证节点间 state 传递（search_queries → raw_results → candidate_papers → ...）。
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from backend.agent.workflows.discovery.graph import build_discovery_graph
from backend.agent.workflows.discovery.nodes import (
    ExpandedQueries,
    RelevanceComment,
)


def _build_mock_llm() -> MagicMock:
    """构建 mock LLM，按节点调用顺序返回结构化输出。

    调用顺序：expand_query → filter_and_rank (per paper)
    """
    responses = [
        # expand_query
        ExpandedQueries(queries=["quantum computing", "quantum error correction"]),
        # filter_and_rank: paper p1
        RelevanceComment(relevance_score=0.95, relevance_comment="Highly relevant"),
        # filter_and_rank: paper p2
        RelevanceComment(relevance_score=0.60, relevance_comment="Somewhat relevant"),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.asyncio
@patch("backend.agent.workflows.discovery.nodes.httpx")
@patch("backend.agent.workflows.discovery.nodes.search_arxiv")
@patch("backend.agent.workflows.discovery.nodes.interrupt")
@patch("backend.agent.workflows.discovery.nodes._save_discovery_feedback")
async def test_discovery_chain_full(
    mock_feedback: MagicMock,
    mock_interrupt: MagicMock,
    mock_arxiv: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    """全链路：expand_query → ... → write_artifacts。

    验证：
    1. expand_query 正确提取 search_queries
    2. search_apis 用每个 query 调用 ArXiv
    3. filter_and_rank 去重并排序
    4. present_candidates 调用 interrupt 并获取 selected_ids
    5. trigger_ingestion 调用 httpx 并返回 document_ids
    6. write_artifacts 输出完整 artifacts 结构
    """
    # Mock ArXiv API
    mock_arxiv.invoke.return_value = [
        {
            "arxiv_id": "2401.00001",
            "title": "Quantum Computing Survey",
            "authors": ["Alice"],
            "abstract": "A survey on quantum computing",
            "year": 2024,
            "source": "arxiv",
        },
        {
            "arxiv_id": "2401.00002",
            "title": "Error Correction",
            "authors": ["Bob"],
            "abstract": "Error correction methods",
            "year": 2024,
            "source": "arxiv",
        },
    ]

    # Mock HITL interrupt
    mock_interrupt.return_value = {"selected_ids": ["2401.00001"]}

    # Mock httpx for trigger_ingestion
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"id": "doc-uuid-1"}
    mock_httpx.post.return_value = mock_response

    # Mock httpx.get for wait_for_ingestion
    mock_status_response = MagicMock()
    mock_status_response.raise_for_status = MagicMock()
    mock_status_response.json.return_value = {"parse_status": "completed"}
    mock_httpx.get.return_value = mock_status_response

    llm = _build_mock_llm()

    graph = build_discovery_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [HumanMessage(content="quantum computing research")],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {},
    }

    config = {"configurable": {"thread_id": "t1", "run_id": "r1"}}
    result = await compiled.ainvoke(input_state, config=config)

    # ── 验证 ArXiv 被调用 ──
    assert mock_arxiv.invoke.call_count == 2  # 两个 query

    # ── 验证 HITL interrupt ──
    mock_interrupt.assert_called_once()

    # ── 验证 httpx.post (trigger_ingestion) ──
    assert mock_httpx.post.call_count == 1  # 只选了 1 篇

    # ── 验证 artifacts 输出 ──
    discovery = result["artifacts"]["discovery"]
    assert len(discovery["papers"]) == 2  # 2 篇 candidate
    assert discovery["selected_paper_ids"] == ["2401.00001"]
    assert len(discovery["ingestion_task_ids"]) == 1
    assert discovery["search_metadata"]["queries"] == [
        "quantum computing",
        "quantum error correction",
    ]
    assert discovery["search_metadata"]["total_raw_results"] >= 2


@pytest.mark.asyncio
@patch("backend.agent.workflows.discovery.nodes.httpx")
@patch("backend.agent.workflows.discovery.nodes.search_arxiv")
@patch("backend.agent.workflows.discovery.nodes.interrupt")
@patch("backend.agent.workflows.discovery.nodes._save_discovery_feedback")
async def test_discovery_chain_empty_selection(
    mock_feedback: MagicMock,
    mock_interrupt: MagicMock,
    mock_arxiv: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    """降级场景：用户不选任何论文 → ingestion_task_ids 为空。"""
    mock_arxiv.invoke.return_value = [
        {
            "arxiv_id": "2401.00001",
            "title": "Paper",
            "authors": [],
            "abstract": "abs",
            "year": 2024,
            "source": "arxiv",
        },
    ]
    mock_interrupt.return_value = {"selected_ids": []}

    responses = [
        ExpandedQueries(queries=["q1"]),
        RelevanceComment(relevance_score=0.5, relevance_comment="ok"),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)

    graph = build_discovery_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [HumanMessage(content="test")],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {},
    }

    config = {"configurable": {"thread_id": "t1", "run_id": "r1"}}
    result = await compiled.ainvoke(input_state, config=config)

    discovery = result["artifacts"]["discovery"]
    assert discovery["selected_paper_ids"] == []
    assert discovery["ingestion_task_ids"] == []
    # httpx.post 不应被调用（无选中论文）
    mock_httpx.post.assert_not_called()
