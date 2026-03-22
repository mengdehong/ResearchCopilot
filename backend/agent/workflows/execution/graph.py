"""Execution WF 子图编排。循环 + HITL + 条件边。"""

from functools import partial
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

if TYPE_CHECKING:
    from backend.services.sandbox_manager import CodeExecutor

from backend.agent.state import ExecutionState, SharedState
from backend.agent.workflows.execution.nodes import (
    execute_sandbox,
    generate_code,
    reflect_and_retry,
    request_confirmation,
    route_execution_result,
    write_artifacts,
)


def build_execution_graph(
    *,
    llm: BaseChatModel,
    executor: "CodeExecutor | None" = None,
) -> StateGraph:
    """构建 Execution 子图。含循环 + HITL + 条件边。"""
    graph = StateGraph(ExecutionState, input_schema=SharedState, output_schema=SharedState)

    graph.add_node("generate_code", partial(generate_code, llm=llm))
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_node(
        "execute_sandbox",
        partial(execute_sandbox, executor=executor) if executor else execute_sandbox,
    )
    graph.add_node("reflect_and_retry", partial(reflect_and_retry, llm=llm))
    graph.add_node("write_artifacts", write_artifacts)

    graph.add_edge(START, "generate_code")
    graph.add_edge("generate_code", "request_confirmation")

    # 条件边：用户确认→执行 / 用户拒绝→直接写 artifacts
    graph.add_conditional_edges(
        "request_confirmation",
        lambda s: "write_artifacts" if s.get("execution_rejected") else "execute_sandbox",
        {"write_artifacts": "write_artifacts", "execute_sandbox": "execute_sandbox"},
    )

    # 条件边：成功→写 artifacts / 失败且有预算→反思重试 / 预算超限→写 artifacts
    graph.add_conditional_edges(
        "execute_sandbox",
        route_execution_result,
        {"write_artifacts": "write_artifacts", "reflect_and_retry": "reflect_and_retry"},
    )

    graph.add_edge("reflect_and_retry", "generate_code")  # 循环回去
    graph.add_edge("write_artifacts", END)

    return graph
