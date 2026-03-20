"""Discovery WF 单元测试。"""

from unittest.mock import MagicMock, patch

from backend.agent.state import PaperCard
from backend.agent.workflows.discovery.graph import build_discovery_graph
from backend.agent.workflows.discovery.nodes import (
    ExpandedQueries,
    RelevanceComment,
    expand_query,
    filter_and_rank,
    present_candidates,
    search_apis,
    trigger_ingestion,
    write_artifacts,
)

# ── Fixtures ──


def _make_mock_llm(responses: list) -> MagicMock:
    """创建 mock LLM，按序返回结构化输出。"""
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_human_message(content: str) -> MagicMock:
    msg = MagicMock()
    msg.type = "human"
    msg.content = content
    return msg


def _make_paper_card(**overrides: object) -> PaperCard:
    defaults = {
        "arxiv_id": "2401.00001",
        "title": "Test Paper",
        "authors": ["Author A"],
        "abstract": "Test abstract",
        "year": 2024,
        "relevance_score": 0.9,
        "relevance_comment": "Highly relevant",
        "source": "arxiv",
    }
    defaults.update(overrides)
    return PaperCard(**defaults)


# ── expand_query ──


def test_expand_query_extracts_queries() -> None:
    llm = _make_mock_llm([ExpandedQueries(queries=["q1", "q2", "q3"])])
    state = {
        "messages": [_make_human_message("transformer attention mechanisms")],
        "discipline": "cs",
    }
    result = expand_query(state, llm=llm)
    assert result["search_queries"] == ["q1", "q2", "q3"]
    llm.with_structured_output.assert_called_once_with(ExpandedQueries)


# ── search_apis ──


@patch("backend.agent.workflows.discovery.nodes.search_arxiv")
def test_search_apis_calls_arxiv_tool(mock_arxiv) -> None:
    mock_arxiv.invoke.return_value = [
        {
            "arxiv_id": "2401.00001",
            "title": "Paper A",
            "authors": [],
            "abstract": "abs",
            "year": 2024,
            "source": "arxiv",
        }
    ]
    state = {"search_queries": ["q1", "q2"]}
    result = search_apis(state)
    assert len(result["raw_results"]) == 2
    assert mock_arxiv.invoke.call_count == 2


# ── filter_and_rank ──


def test_filter_and_rank_deduplicates() -> None:
    """重复 arxiv_id 应去重。"""
    llm = _make_mock_llm(
        [
            RelevanceComment(relevance_score=0.8, relevance_comment="Good"),
        ]
    )
    state = {
        "raw_results": [
            {
                "arxiv_id": "2401.00001",
                "title": "Paper A",
                "authors": [],
                "abstract": "abs",
                "year": 2024,
                "source": "arxiv",
            },
            {
                "arxiv_id": "2401.00001",
                "title": "Paper A dup",
                "authors": [],
                "abstract": "abs",
                "year": 2024,
                "source": "arxiv",
            },
        ],
        "discipline": "cs",
    }
    result = filter_and_rank(state, llm=llm)
    assert len(result["candidate_papers"]) == 1


def test_filter_and_rank_sorts_by_relevance() -> None:
    """应按 relevance_score 降序排列。"""
    llm = _make_mock_llm(
        [
            RelevanceComment(relevance_score=0.3, relevance_comment="Low"),
            RelevanceComment(relevance_score=0.9, relevance_comment="High"),
        ]
    )
    state = {
        "raw_results": [
            {
                "arxiv_id": "2401.00001",
                "title": "Low",
                "authors": [],
                "abstract": "a",
                "year": 2024,
                "source": "arxiv",
            },
            {
                "arxiv_id": "2401.00002",
                "title": "High",
                "authors": [],
                "abstract": "b",
                "year": 2024,
                "source": "arxiv",
            },
        ],
        "discipline": "cs",
    }
    result = filter_and_rank(state, llm=llm)
    scores = [p.relevance_score for p in result["candidate_papers"]]
    assert scores == [0.9, 0.3]


# ── present_candidates (HITL) ──


def test_present_candidates_returns_selected_ids() -> None:
    papers = [_make_paper_card(arxiv_id="p1"), _make_paper_card(arxiv_id="p2")]
    state = {"candidate_papers": papers}
    with patch(
        "backend.agent.workflows.discovery.nodes.interrupt",
        return_value={"selected_ids": ["p1"]},
    ):
        result = present_candidates(state)
    assert result["selected_paper_ids"] == ["p1"]


# ── trigger_ingestion ──


@patch("backend.agent.workflows.discovery.nodes.httpx")
def test_trigger_ingestion_creates_task_ids(mock_httpx) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response
    state = {"selected_paper_ids": ["p1", "p2"]}
    result = trigger_ingestion(state)
    assert len(result["ingestion_task_ids"]) == 2
    assert result["ingestion_task_ids"] == ["p1", "p2"]


# ── write_artifacts ──


def test_write_artifacts_structure() -> None:
    papers = [_make_paper_card()]
    state = {
        "candidate_papers": papers,
        "selected_paper_ids": ["2401.00001"],
        "ingestion_task_ids": ["task_2401.00001"],
        "search_queries": ["q1"],
        "raw_results": [{"arxiv_id": "2401.00001"}],
    }
    result = write_artifacts(state)
    discovery = result["artifacts"]["discovery"]
    assert len(discovery["papers"]) == 1
    assert discovery["selected_paper_ids"] == ["2401.00001"]
    assert discovery["search_metadata"]["queries"] == ["q1"]
    assert discovery["search_metadata"]["total_raw_results"] == 1


# ── Subgraph 编译 ──


def test_discovery_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_discovery_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "expand_query" in node_names
    assert "present_candidates" in node_names
    assert "write_artifacts" in node_names
