"""Critique WF 单元测试。"""
from unittest.mock import MagicMock

from backend.agent.state import CritiqueFeedback
from backend.agent.workflows.critique.graph import build_critique_graph
from backend.agent.workflows.critique.nodes import (
    CriticReview,
    JudgeVerdict,
    SupporterReview,
    critic_review,
    judge_verdict,
    supporter_review,
    write_artifacts,
)


def _make_mock_llm(responses: list) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


# ── supporter_review ──

def test_supporter_review_returns_opinion() -> None:
    llm = _make_mock_llm([
        SupporterReview(opinion="Strong methodology", strengths=["s1"]),
    ])
    state = {
        "target_workflow": "extraction",
        "artifacts": {"extraction": {"notes": "good notes"}},
    }
    result = supporter_review(state, llm=llm)
    assert "methodology" in result["supporter_opinion"].lower()


# ── critic_review ──

def test_critic_review_returns_opinion() -> None:
    llm = _make_mock_llm([
        CriticReview(opinion="Missing ablation study", weaknesses=["w1"]),
    ])
    state = {
        "target_workflow": "extraction",
        "artifacts": {"extraction": {"notes": "notes"}},
    }
    result = critic_review(state, llm=llm)
    assert result["critic_opinion"]


# ── judge_verdict ──

def test_judge_verdict_pass() -> None:
    llm = _make_mock_llm([
        JudgeVerdict(verdict="pass", feedbacks=[], summary="All good"),
    ])
    state = {
        "target_workflow": "extraction",
        "supporter_opinion": "good",
        "critic_opinion": "minor issues",
    }
    result = judge_verdict(state, llm=llm)
    assert result["verdict"] == "pass"
    assert result["feedbacks"] == []


def test_judge_verdict_revise() -> None:
    feedback = CritiqueFeedback(
        category="methodology", severity="major",
        description="Missing baseline comparison",
        suggestion="Add ablation study",
    )
    llm = _make_mock_llm([
        JudgeVerdict(verdict="revise", feedbacks=[feedback], summary="Needs work"),
    ])
    state = {
        "target_workflow": "ideation",
        "supporter_opinion": "ok",
        "critic_opinion": "problems",
    }
    result = judge_verdict(state, llm=llm)
    assert result["verdict"] == "revise"
    assert len(result["feedbacks"]) == 1


# ── write_artifacts ──

def test_critique_write_artifacts_structure() -> None:
    feedback = CritiqueFeedback(
        category="logic", severity="minor",
        description="test", suggestion="fix",
    )
    state = {
        "target_workflow": "extraction",
        "verdict": "pass",
        "feedbacks": [feedback],
        "critique_round": 1,
        "supporter_opinion": "good",
        "critic_opinion": "ok",
    }
    result = write_artifacts(state)
    critique = result["artifacts"]["critique"]
    assert "extraction" in critique
    assert critique["extraction"]["verdict"] == "pass"


# ── Subgraph 编译 ──

def test_critique_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_critique_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "supporter_review" in node_names
    assert "critic_review" in node_names
    assert "judge_verdict" in node_names
