"""Supervisor 路由评分函数单元测试。"""

from unittest.mock import MagicMock

from backend.agent.optimizers.metrics.supervisor_metric import (
    supervisor_routing_metric,
)
from backend.agent.routing import RouteDecision
from backend.agent.state import ExecutionPlan, PlannedStep


def _make_example(decision: RouteDecision) -> MagicMock:
    """创建 DSPy Example mock。"""
    ex = MagicMock()
    ex.routing_decision = decision
    return ex


# ── Mode 匹配测试 ──


def test_mode_mismatch_returns_zero() -> None:
    """mode 不匹配应返回 0 分。"""
    expected = _make_example(
        RouteDecision(mode="single", target_workflow="discovery", reasoning="test")
    )
    predicted = _make_example(RouteDecision(mode="chat", reasoning="wrong"))
    assert supervisor_routing_metric(expected, predicted) == 0.0


# ── Single 模式测试 ──


def test_single_mode_exact_match() -> None:
    """single 模式完全匹配应得 1.0 分。"""
    expected = _make_example(
        RouteDecision(mode="single", target_workflow="discovery", reasoning="test")
    )
    predicted = _make_example(
        RouteDecision(mode="single", target_workflow="discovery", reasoning="test")
    )
    assert supervisor_routing_metric(expected, predicted) == 1.0


def test_single_mode_wrong_workflow() -> None:
    """single 模式 workflow 不匹配只得 0.4 分（mode 分）。"""
    expected = _make_example(
        RouteDecision(mode="single", target_workflow="discovery", reasoning="test")
    )
    predicted = _make_example(
        RouteDecision(mode="single", target_workflow="extraction", reasoning="test")
    )
    assert supervisor_routing_metric(expected, predicted) == 0.4


# ── Chat 模式测试 ──


def test_chat_mode_match() -> None:
    """chat 模式匹配应得满分 1.0。"""
    expected = _make_example(RouteDecision(mode="chat", reasoning="greeting"))
    predicted = _make_example(RouteDecision(mode="chat", reasoning="greeting"))
    assert supervisor_routing_metric(expected, predicted) == 1.0


# ── Plan 模式测试 ──


def test_plan_mode_exact_first_step_and_length() -> None:
    """plan 模式：首步匹配 + 步数接近应得 1.0 分。"""
    plan = ExecutionPlan(
        goal="test",
        steps=[
            PlannedStep(
                workflow="discovery",
                objective="search",
                success_criteria="found papers",
            ),
            PlannedStep(
                workflow="extraction",
                objective="read",
                success_criteria="extracted info",
            ),
        ],
    )
    expected = _make_example(RouteDecision(mode="plan", reasoning="test", plan=plan))
    predicted = _make_example(RouteDecision(mode="plan", reasoning="test", plan=plan))
    assert supervisor_routing_metric(expected, predicted) == 1.0


def test_plan_mode_wrong_first_step() -> None:
    """plan 模式首步不匹配：mode 0.4 + 步数 0.3 = 0.7。"""
    expected_plan = ExecutionPlan(
        goal="test",
        steps=[
            PlannedStep(
                workflow="discovery",
                objective="s",
                success_criteria="c",
            ),
        ],
    )
    predicted_plan = ExecutionPlan(
        goal="test",
        steps=[
            PlannedStep(
                workflow="extraction",
                objective="s",
                success_criteria="c",
            ),
        ],
    )
    expected = _make_example(RouteDecision(mode="plan", reasoning="test", plan=expected_plan))
    predicted = _make_example(RouteDecision(mode="plan", reasoning="test", plan=predicted_plan))
    assert supervisor_routing_metric(expected, predicted) == 0.7


def test_plan_mode_no_plan_gets_mode_score_only() -> None:
    """plan 模式但 plan 为 None：只得 mode 分 0.4。"""
    expected = _make_example(RouteDecision(mode="plan", reasoning="t", plan=None))
    predicted = _make_example(RouteDecision(mode="plan", reasoning="t", plan=None))
    assert supervisor_routing_metric(expected, predicted) == 0.4
