"""Discovery WF 子图编排。线性 + HITL：expand_query → search_apis → filter_and_rank → present_candidates → trigger_ingestion → write_artifacts。"""
from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from backend.agent.state import DiscoveryState, SharedState
from backend.agent.workflows.discovery.nodes import (
    expand_query,
    filter_and_rank,
    present_candidates,
    search_apis,
    trigger_ingestion,
    write_artifacts,
)


def build_discovery_graph(*, llm: BaseChatModel) -> StateGraph:
    """构建 Discovery 子图。

    Args:
        llm: LLM 实例，用于 expand_query 和 filter_and_rank 节点。
    """
    graph = StateGraph(DiscoveryState, input_schema=SharedState, output_schema=SharedState)

    graph.add_node("expand_query", partial(expand_query, llm=llm))
    graph.add_node("search_apis", search_apis)
    graph.add_node("filter_and_rank", partial(filter_and_rank, llm=llm))
    graph.add_node("present_candidates", present_candidates)
    graph.add_node("trigger_ingestion", trigger_ingestion)
    graph.add_node("write_artifacts", write_artifacts)

    graph.add_edge(START, "expand_query")
    graph.add_edge("expand_query", "search_apis")
    graph.add_edge("search_apis", "filter_and_rank")
    graph.add_edge("filter_and_rank", "present_candidates")
    graph.add_edge("present_candidates", "trigger_ingestion")
    graph.add_edge("trigger_ingestion", "write_artifacts")
    graph.add_edge("write_artifacts", END)

    return graph
