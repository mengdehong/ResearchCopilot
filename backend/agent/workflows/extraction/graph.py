"""Extraction WF 子图编排。wait_rag_ready → check_existing_notes →（增量路由）→ retrieve → ... → write_artifacts。"""

from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.agent.state import ExtractionState, SharedState
from backend.agent.workflows.extraction.nodes import (
    build_glossary,
    check_existing_notes,
    cross_compare,
    generate_notes,
    retrieve_chunks,
    wait_rag_ready,
    write_artifacts,
)
from backend.services.rag_engine import RAGEngine


def _route_after_check(state: ExtractionState) -> str:
    """增量路由：paper_ids 为空时跳过检索直接写 artifacts。"""
    return "write_artifacts" if not state.get("paper_ids") else "retrieve_chunks"


def build_extraction_graph(
    *,
    llm: BaseChatModel,
    rag_engine: RAGEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> StateGraph:
    """构建 Extraction 子图。"""
    graph = StateGraph(ExtractionState, input_schema=SharedState, output_schema=SharedState)

    graph.add_node("wait_rag_ready", wait_rag_ready)
    graph.add_node("check_existing_notes", check_existing_notes)
    graph.add_node(
        "retrieve_chunks",
        partial(retrieve_chunks, rag_engine=rag_engine, session_factory=session_factory),
    )
    graph.add_node("generate_notes", partial(generate_notes, llm=llm))
    graph.add_node("cross_compare", partial(cross_compare, llm=llm))
    graph.add_node("build_glossary", partial(build_glossary, llm=llm))
    graph.add_node("write_artifacts", write_artifacts)

    graph.add_edge(START, "wait_rag_ready")
    graph.add_edge("wait_rag_ready", "check_existing_notes")
    graph.add_conditional_edges(
        "check_existing_notes",
        _route_after_check,
        {"retrieve_chunks": "retrieve_chunks", "write_artifacts": "write_artifacts"},
    )
    graph.add_edge("retrieve_chunks", "generate_notes")
    graph.add_edge("generate_notes", "cross_compare")
    graph.add_edge("cross_compare", "build_glossary")
    graph.add_edge("build_glossary", "write_artifacts")
    graph.add_edge("write_artifacts", END)

    return graph
