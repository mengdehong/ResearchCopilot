"""Critique WF 子图编排。Send() 并行 fan-out：supporter + critic → judge → write_artifacts。"""

from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.agent.state import CritiqueState, SharedState
from backend.agent.workflows.critique.nodes import (
    critic_review,
    judge_verdict,
    supporter_review,
    write_artifacts,
)


def _fan_out_reviews(state: CritiqueState) -> list[Send]:
    """Supporter 和 Critic 并行执行，互不可见。"""
    return [
        Send("supporter_review", state),
        Send("critic_review", state),
    ]


def build_critique_graph(*, llm: BaseChatModel) -> StateGraph:
    """构建 Critique 子图。含 Send() 并行 fan-out。"""
    graph = StateGraph(CritiqueState, input_schema=SharedState, output_schema=SharedState)

    graph.add_node("supporter_review", partial(supporter_review, llm=llm))
    graph.add_node("critic_review", partial(critic_review, llm=llm))
    graph.add_node("judge_verdict", partial(judge_verdict, llm=llm))
    graph.add_node("write_artifacts", write_artifacts)

    # 并行 fan-out
    graph.add_conditional_edges(START, _fan_out_reviews)

    # 两方完成后汇聚到裁决
    graph.add_edge("supporter_review", "judge_verdict")
    graph.add_edge("critic_review", "judge_verdict")
    graph.add_edge("judge_verdict", "write_artifacts")
    graph.add_edge("write_artifacts", END)

    return graph
