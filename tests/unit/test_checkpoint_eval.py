"""检查点回评逻辑单元测试。覆盖 pass→advance / fail→replan / fail→retry_same 三条路径。"""

from unittest.mock import MagicMock

import pytest

from backend.agent.graph import MAX_STEP_RETRIES, _build_checkpoint_eval_node
from backend.agent.routing import StepEvaluation
from backend.agent.state import ExecutionPlan, PlannedStep


def _make_plan(steps: list[tuple[str, str, str]]) -> ExecutionPlan:
    """构建测试用 ExecutionPlan。steps = [(workflow, objective, criteria), ...]"""
    return ExecutionPlan(
        steps=[PlannedStep(workflow=w, objective=o, success_criteria=c) for w, o, c in steps],
        goal="test",
    )


def _make_mock_llm(evaluation: StepEvaluation) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(return_value=evaluation)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


# ── pass → advance ──


@pytest.mark.unit
def test_checkpoint_eval_pass_advances_to_next_step() -> None:
    """评估通过时应推进到下一步。"""
    llm = _make_mock_llm(StepEvaluation(passed=True, reason="artifacts complete"))
    node = _build_checkpoint_eval_node(llm)

    plan = _make_plan(
        [
            ("discovery", "search papers", "papers found"),
            ("extraction", "extract notes", "notes generated"),
        ]
    )
    state = {
        "plan": plan,
        "current_step_index": 0,
        "artifacts": {"discovery": {"papers": ["p1"]}},
    }

    result = node(state)
    assert result["routing_decision"] == "extraction"
    assert result["current_step_index"] == 1


@pytest.mark.unit
def test_checkpoint_eval_pass_last_step_ends() -> None:
    """最后一步通过时应结束。"""
    llm = _make_mock_llm(StepEvaluation(passed=True, reason="done"))
    node = _build_checkpoint_eval_node(llm)

    plan = _make_plan([("discovery", "search papers", "papers found")])
    state = {"plan": plan, "current_step_index": 0, "artifacts": {}}

    result = node(state)
    assert result["routing_decision"] == "__end__"


# ── fail → replan ──


@pytest.mark.unit
def test_checkpoint_eval_fail_replans() -> None:
    """评估不通过且不重试时应回 supervisor 重规划。"""
    llm = _make_mock_llm(StepEvaluation(passed=False, reason="criteria not met", retry_same=False))
    node = _build_checkpoint_eval_node(llm)

    plan = _make_plan([("discovery", "search papers", "papers found")])
    state = {"plan": plan, "current_step_index": 0, "artifacts": {}}

    result = node(state)
    assert result["routing_decision"] == "__replan__"
    assert result["plan"] is None


# ── fail → retry_same ──


@pytest.mark.unit
def test_checkpoint_eval_fail_retry_same() -> None:
    """评估不通过但建议重试时应重试当前步骤。"""
    llm = _make_mock_llm(StepEvaluation(passed=False, reason="partial output", retry_same=True))
    node = _build_checkpoint_eval_node(llm)

    plan = _make_plan([("discovery", "search papers", "papers found")])
    state = {"plan": plan, "current_step_index": 0, "artifacts": {}, "_step_retry_count": 0}

    result = node(state)
    assert result["routing_decision"] == "discovery"
    assert result["current_step_index"] == 0
    assert result["_step_retry_count"] == 1


@pytest.mark.unit
def test_checkpoint_eval_retry_max_falls_back_to_replan() -> None:
    """重试次数达上限时应回退到 replan。"""
    llm = _make_mock_llm(StepEvaluation(passed=False, reason="still failing", retry_same=True))
    node = _build_checkpoint_eval_node(llm)

    plan = _make_plan([("discovery", "search papers", "papers found")])
    state = {
        "plan": plan,
        "current_step_index": 0,
        "artifacts": {},
        "_step_retry_count": MAX_STEP_RETRIES,
    }

    result = node(state)
    assert result["routing_decision"] == "__replan__"


# ── no plan → end ──


@pytest.mark.unit
def test_checkpoint_eval_no_plan_ends() -> None:
    """无计划时应直接结束。"""
    llm = _make_mock_llm(StepEvaluation(passed=True, reason="n/a"))
    node = _build_checkpoint_eval_node(llm)

    state = {"plan": None, "current_step_index": 0, "artifacts": {}}
    result = node(state)
    assert result["routing_decision"] == "__end__"
