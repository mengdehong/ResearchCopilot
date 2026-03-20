"""Publish WF 子图编排。线性 + HITL：assemble_outline → generate_markdown → request_finalization → render_presentation → package_zip → write_artifacts。"""

from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from backend.agent.state import PublishState, SharedState
from backend.agent.workflows.publish.nodes import (
    assemble_outline,
    generate_markdown,
    package_zip,
    render_presentation,
    request_finalization,
    write_artifacts,
)


def build_publish_graph(*, llm: BaseChatModel) -> StateGraph:
    """构建 Publish 子图。含 HITL approve/reject 双路径。"""
    graph = StateGraph(PublishState, input_schema=SharedState, output_schema=SharedState)

    graph.add_node("assemble_outline", partial(assemble_outline, llm=llm))
    graph.add_node("generate_markdown", partial(generate_markdown, llm=llm))
    graph.add_node("request_finalization", request_finalization)
    graph.add_node("render_presentation", render_presentation)
    graph.add_node("package_zip", package_zip)
    graph.add_node("write_artifacts", write_artifacts)

    graph.add_edge(START, "assemble_outline")
    graph.add_edge("assemble_outline", "generate_markdown")
    graph.add_edge("generate_markdown", "request_finalization")
    graph.add_edge("request_finalization", "render_presentation")
    graph.add_edge("render_presentation", "package_zip")
    graph.add_edge("package_zip", "write_artifacts")
    graph.add_edge("write_artifacts", END)

    return graph
