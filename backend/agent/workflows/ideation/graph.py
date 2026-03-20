"""Ideation WF 子图编排。线性：analyze_gaps → generate_designs → select_design → write_artifacts。"""
from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from backend.agent.state import IdeationState, SharedState
from backend.agent.workflows.ideation.nodes import (
    analyze_gaps,
    generate_designs,
    select_design,
    write_artifacts,
)


def build_ideation_graph(*, llm: BaseChatModel) -> StateGraph:
    """构建 Ideation 子图。"""
    graph = StateGraph(IdeationState, input_schema=SharedState, output_schema=SharedState)

    graph.add_node("analyze_gaps", partial(analyze_gaps, llm=llm))
    graph.add_node("generate_designs", partial(generate_designs, llm=llm))
    graph.add_node("select_design", partial(select_design, llm=llm))
    graph.add_node("write_artifacts", write_artifacts)

    graph.add_edge(START, "analyze_gaps")
    graph.add_edge("analyze_gaps", "generate_designs")
    graph.add_edge("generate_designs", "select_design")
    graph.add_edge("select_design", "write_artifacts")
    graph.add_edge("write_artifacts", END)

    return graph
