"""Critique WF 全链路测试。

编译完整的 Critique 子图，端到端验证 Send() 并行 fan-out：
  supporter_review ∥ critic_review → judge_verdict → write_artifacts

LLM 使用 mock，但通过真实 LangGraph 图执行，
验证 Send() 并行分发和 reducer 汇聚后 judge_verdict 接收双方意见。
"""

from unittest.mock import MagicMock

import pytest

from backend.agent.state import CritiqueFeedback
from backend.agent.workflows.critique.graph import build_critique_graph
from backend.agent.workflows.critique.nodes import (
    CriticReview,
    JudgeVerdict,
    SupporterReview,
)


def _build_mock_llm_pass() -> MagicMock:
    """构建 mock LLM：verdict = pass。

    调用顺序：supporter_review, critic_review (Send 并行), judge_verdict
    注意 Send() 导致两方可能任意顺序，所以用 side_effect list
    需要确保 supporter 和 critic 各调用一次 LLM。
    """
    responses = [
        # supporter_review
        SupporterReview(opinion="Strong methodology and clear results", strengths=["s1", "s2"]),
        # critic_review
        CriticReview(opinion="Minor concerns about sample size", weaknesses=["w1"]),
        # judge_verdict
        JudgeVerdict(verdict="pass", feedbacks=[], summary="Overall acceptable"),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _build_mock_llm_revise() -> MagicMock:
    """构建 mock LLM：verdict = revise with feedbacks。"""
    feedback = CritiqueFeedback(
        category="methodology",
        severity="major",
        description="Missing ablation study",
        suggestion="Add ablation experiments for key components",
    )
    responses = [
        SupporterReview(opinion="Some strengths", strengths=["s1"]),
        CriticReview(opinion="Significant methodology gaps", weaknesses=["w1", "w2"]),
        JudgeVerdict(
            verdict="revise",
            feedbacks=[feedback],
            summary="Needs revision before acceptance",
        ),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.asyncio
async def test_critique_chain_pass() -> None:
    """全链路：Send() fan-out → judge pass → artifacts 正确。

    验证：
    1. supporter_review 和 critic_review 均被执行（共 3 次 LLM 调用）
    2. judge_verdict 收到双方意见后输出 pass
    3. artifacts["critique"] 包含完整结构
    """
    llm = _build_mock_llm_pass()
    graph = build_critique_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {
            "extraction": {"reading_notes": [{"paper_id": "p1", "key_contributions": ["c1"]}]},
        },
        "target_workflow": "extraction",
        "critique_round": 1,
    }

    result = await compiled.ainvoke(input_state)

    # ── 验证 LLM 被调用 3 次 ──
    structured = llm.with_structured_output.return_value
    assert structured.invoke.call_count == 3

    # ── 验证 artifacts ──
    critique = result["artifacts"]["critique"]
    assert "extraction" in critique
    assert critique["extraction"]["verdict"] == "pass"
    assert critique["extraction"]["feedbacks"] == []
    assert critique["extraction"]["round"] == 1
    assert critique["extraction"]["supporter_opinion"]
    assert critique["extraction"]["critic_opinion"]


@pytest.mark.asyncio
async def test_critique_chain_revise() -> None:
    """全链路：Send() fan-out → judge revise → feedbacks 非空。"""
    llm = _build_mock_llm_revise()
    graph = build_critique_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {
            "ideation": {"research_gaps": [{"description": "gap1"}]},
        },
        "target_workflow": "ideation",
        "critique_round": 2,
    }

    result = await compiled.ainvoke(input_state)

    critique = result["artifacts"]["critique"]
    assert critique["ideation"]["verdict"] == "revise"
    assert len(critique["ideation"]["feedbacks"]) == 1
    assert critique["ideation"]["feedbacks"][0]["category"] == "methodology"
    assert critique["ideation"]["round"] == 2
