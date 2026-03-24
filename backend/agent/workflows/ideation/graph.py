"""Ideation WF 子图编排。三步 CoT + 方案生成：decompose → reason → synthesize → generate → select → write_artifacts。"""

from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from backend.agent.state import IdeationState, SharedState
from backend.agent.workflows.ideation.nodes import (
    decompose_problem,
    generate_designs,
    reason_evidence,
    select_design,
    synthesize_gaps,
    write_artifacts,
)


def build_ideation_graph(*, llm: BaseChatModel) -> StateGraph:
    """构建 Ideation 子图。"""
    graph = StateGraph(IdeationState, input_schema=SharedState, output_schema=SharedState)

    graph.add_node("decompose_problem", partial(decompose_problem, llm=llm))
    graph.add_node("reason_evidence", partial(reason_evidence, llm=llm))
    graph.add_node("synthesize_gaps", partial(synthesize_gaps, llm=llm))
    graph.add_node("generate_designs", partial(generate_designs, llm=llm))
    graph.add_node("select_design", partial(select_design, llm=llm))
    graph.add_node("write_artifacts", write_artifacts)

    graph.add_edge(START, "decompose_problem")
    graph.add_edge("decompose_problem", "reason_evidence")
    graph.add_edge("reason_evidence", "synthesize_gaps")
    graph.add_edge("synthesize_gaps", "generate_designs")
    graph.add_edge("generate_designs", "select_design")
    graph.add_edge("select_design", "write_artifacts")
    graph.add_edge("write_artifacts", END)

    return graph
