"""Supervisor 主图构建测试。"""
import pytest
from pydantic import ValidationError

from backend.agent.graph import WORKFLOW_NAMES, _checkpoint_eval_node, build_supervisor_graph
from backend.agent.state import ExecutionPlan, PlannedStep


def test_build_supervisor_graph_compiles() -> None:
    graph = build_supervisor_graph()
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    # 8 业务节点 + __start__ + __end__
    assert "supervisor" in node_names
    assert "checkpoint_eval" in node_names
    for wf in WORKFLOW_NAMES:
        assert wf in node_names


def test_supervisor_default_routes_to_end() -> None:
    graph = build_supervisor_graph()
    compiled = graph.compile()
    result = compiled.invoke({
        "messages": [],
        "workspace_id": "test",
        "discipline": "cs",
        "artifacts": {},
        "plan": None,
        "current_step_index": 0,
        "routing_decision": None,
    })
    # placeholder supervisor 默认路由到 __end__
    assert result["routing_decision"] == "__end__"


def test_checkpoint_advances_index_on_completion() -> None:
    """完成最后一步时 current_step_index 应前进。"""
    plan = ExecutionPlan(
        goal="test",
        steps=[PlannedStep(workflow="discovery", objective="find", success_criteria="found")],
    )
    state = {"plan": plan, "current_step_index": 0}
    result = _checkpoint_eval_node(state)
    assert result["routing_decision"] == "__end__"
    assert result["current_step_index"] == 1


def test_planned_step_rejects_invalid_workflow() -> None:
    """PlannedStep.workflow 应拒绝无效的 workflow 名称。"""
    with pytest.raises(ValidationError):
        PlannedStep(workflow="typo", objective="x", success_criteria="y")

