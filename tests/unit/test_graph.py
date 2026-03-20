"""Supervisor 主图构建测试。"""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from backend.agent.graph import WORKFLOW_NAMES, build_supervisor_graph
from backend.agent.routing import RouteDecision
from backend.agent.state import PlannedStep


def _make_mock_llm(responses: list | None = None) -> MagicMock:
    """创建 mock LLM。"""
    llm = MagicMock()
    structured = MagicMock()
    if responses:
        structured.invoke = MagicMock(side_effect=responses)
    else:
        structured.invoke = MagicMock(
            return_value=RouteDecision(
                mode="single",
                target_workflow=None,
                plan=None,
                reasoning="end",
            )
        )
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def test_build_supervisor_graph_compiles() -> None:
    llm = _make_mock_llm()
    graph = build_supervisor_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "supervisor" in node_names
    assert "checkpoint_eval" in node_names
    for wf in WORKFLOW_NAMES:
        assert wf in node_names


def test_supervisor_routes_to_end_with_none_target() -> None:
    """Supervisor LLM 返回 mode=single target=None → 路由到 __end__。"""
    llm = _make_mock_llm(
        [
            RouteDecision(mode="single", target_workflow=None, plan=None, reasoning="done"),
        ]
    )
    graph = build_supervisor_graph(llm=llm)
    compiled = graph.compile()
    result = compiled.invoke(
        {
            "messages": [],
            "workspace_id": "test",
            "discipline": "cs",
            "artifacts": {},
            "plan": None,
            "current_step_index": 0,
            "routing_decision": None,
        }
    )
    assert result["routing_decision"] == "__end__"


def test_planned_step_rejects_invalid_workflow() -> None:
    """PlannedStep.workflow 应拒绝无效的 workflow 名称。"""
    with pytest.raises(ValidationError):
        PlannedStep(workflow="typo", objective="x", success_criteria="y")
