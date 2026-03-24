"""Critique WF 节点函数。模拟审稿：红蓝并行对抗 + 裁决合并。"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.agent.prompts.loader import load_prompt
from backend.agent.state import CritiqueFeedback, CritiqueState
from backend.core.logger import get_logger

logger = get_logger(__name__)


# ── LLM 输出结构 ──


class SupporterReview(BaseModel):
    """蓝方正面评价。"""

    opinion: str
    strengths: list[str]


class CriticReview(BaseModel):
    """红方质疑。"""

    opinion: str
    weaknesses: list[str]


class JudgeVerdict(BaseModel):
    """裁决结果。"""

    verdict: str  # "pass" | "revise"
    feedbacks: list[CritiqueFeedback]
    summary: str


# ── 节点函数 ──


def _get_target_artifacts(state: CritiqueState) -> str:
    """提取审查目标 WF 的 artifacts 内容。"""
    target_wf = state.get("target_workflow", "")
    artifacts = state.get("artifacts", {})
    target_data = artifacts.get(target_wf, {})
    return json.dumps(target_data, ensure_ascii=False, default=str)


def supporter_review(
    state: CritiqueState,
    *,
    llm: BaseChatModel,
) -> dict:
    """蓝方（支持者）独立评审：只看原始产出物，正面评价。"""
    target_content = _get_target_artifacts(state)
    target_wf = state.get("target_workflow", "")

    prompt = load_prompt(
        "critique/prompts",
        key="supporter_review",
        variables={
            "target_wf": target_wf,
            "target_content": target_content,
        },
    )
    result = llm.with_structured_output(SupporterReview).invoke(
        [
            SystemMessage(content=prompt["system"]),
            HumanMessage(content=prompt["user"]),
        ]
    )

    logger.info("supporter_review_done", target=target_wf)
    return {"supporter_opinion": result.opinion}


def critic_review(
    state: CritiqueState,
    *,
    llm: BaseChatModel,
) -> dict:
    """红方（批评者）独立评审：只看原始产出物，质疑和问题。"""
    target_content = _get_target_artifacts(state)
    target_wf = state.get("target_workflow", "")

    prompt = load_prompt(
        "critique/prompts",
        key="critic_review",
        variables={
            "target_wf": target_wf,
            "target_content": target_content,
        },
    )
    result = llm.with_structured_output(CriticReview).invoke(
        [
            SystemMessage(content=prompt["system"]),
            HumanMessage(content=prompt["user"]),
        ]
    )

    logger.info("critic_review_done", target=target_wf)
    return {"critic_opinion": result.opinion}


def judge_verdict(
    state: CritiqueState,
    *,
    llm: BaseChatModel,
) -> dict:
    """裁决节点：合并红蓝双方意见，输出 verdict + feedbacks。"""
    target_wf = state.get("target_workflow", "")
    supporter = state.get("supporter_opinion", "")
    critic = state.get("critic_opinion", "")

    context = json.dumps(
        {
            "target_workflow": target_wf,
            "supporter_opinion": supporter,
            "critic_opinion": critic,
        },
        ensure_ascii=False,
    )

    result = llm.with_structured_output(JudgeVerdict).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "critique/prompts",
                    key="judge_verdict",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    logger.info(
        "judge_verdict_done",
        target=target_wf,
        verdict=result.verdict,
        feedback_count=len(result.feedbacks),
    )
    return {
        "verdict": result.verdict,
        "feedbacks": result.feedbacks,
    }


def write_artifacts(state: CritiqueState) -> dict:
    """将 Critique 产出物写入 artifacts 命名空间，按审查目标分 key。"""
    target_wf = state.get("target_workflow", "")
    return {
        "artifacts": {
            "critique": {
                target_wf: {
                    "verdict": state.get("verdict", ""),
                    "feedbacks": [f.model_dump() for f in state.get("feedbacks", [])],
                    "round": state.get("critique_round", 1),
                    "supporter_opinion": state.get("supporter_opinion", ""),
                    "critic_opinion": state.get("critic_opinion", ""),
                },
            },
        },
    }
