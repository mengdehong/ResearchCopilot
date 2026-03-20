"""Supervisor 主图编排。连接硬规则路由、LLM 路由、检查点回评和 6 个 WF subgraph。"""
from langgraph.graph import END, START, StateGraph

from backend.agent.routing import route_after_eval, route_to_workflow
from backend.agent.state import SupervisorState
from backend.core.logger import get_logger

logger = get_logger(__name__)


# WF subgraph placeholder（Phase 4 替换为真实实现）
def _placeholder_node(state: dict) -> dict:
    """占位 WF 节点。Phase 4 替换为真实 subgraph。"""
    return {"artifacts": {}}


def _supervisor_node(state: dict) -> dict:
    """Supervisor 主控节点占位。Phase 4 填充 LLM 路由逻辑。"""
    routing_decision = "__end__"
    logger.info(
        "routing_decision",
        target=routing_decision,
        mode="placeholder",
        reasoning="Phase 4 will implement LLM routing",
    )
    return {"routing_decision": routing_decision, "current_step_index": 0}


def _checkpoint_eval_node(state: dict) -> dict:
    """检查点回评节点占位。Phase 4 填充 LLM 评估逻辑。"""
    plan = state.get("plan")
    step_index = state.get("current_step_index", 0)

    if plan and step_index + 1 < len(plan.steps):
        next_wf = plan.steps[step_index + 1].workflow
        logger.info(
            "checkpoint_eval",
            step_index=step_index,
            passed=True,
            reason="advancing to next step",
        )
        return {
            "routing_decision": next_wf,
            "current_step_index": step_index + 1,
        }
    logger.info(
        "checkpoint_eval",
        step_index=step_index,
        passed=True,
        reason="plan complete",
    )
    return {"routing_decision": "__end__", "current_step_index": step_index + 1}


WORKFLOW_NAMES = ["discovery", "extraction", "ideation", "execution", "critique", "publish"]


def build_supervisor_graph() -> StateGraph:
    """构建 Supervisor 主图。"""
    graph = StateGraph(SupervisorState)

    # 节点注册
    graph.add_node("supervisor", _supervisor_node)
    graph.add_node("checkpoint_eval", _checkpoint_eval_node)

    for wf in WORKFLOW_NAMES:
        graph.add_node(wf, _placeholder_node)

    # 边连接
    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges(
        "supervisor", route_to_workflow,
        {wf: wf for wf in WORKFLOW_NAMES} | {"__end__": END},
    )

    for wf in WORKFLOW_NAMES:
        graph.add_edge(wf, "checkpoint_eval")

    graph.add_conditional_edges(
        "checkpoint_eval", route_after_eval,
        {wf: wf for wf in WORKFLOW_NAMES} | {"supervisor": "supervisor", "__end__": END},
    )

    return graph
