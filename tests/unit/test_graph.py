"""Supervisor 主图构建测试。"""
from backend.agent.graph import WORKFLOW_NAMES, build_supervisor_graph


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
