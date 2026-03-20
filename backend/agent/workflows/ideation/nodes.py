"""Ideation WF 节点函数。实验推演：分析 Gap → 生成方案 → 推荐排序 → 写 artifacts。"""
import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.agent.prompts.loader import load_prompt
from backend.agent.state import ExperimentDesign, IdeationState, ResearchGap
from backend.core.logger import get_logger

logger = get_logger(__name__)


# ── LLM 输出结构 ──

class GapAnalysisResult(BaseModel):
    """LLM 分析的 Research Gap 列表。"""
    gaps: list[ResearchGap]


class DesignGenerationResult(BaseModel):
    """LLM 生成的实验方案列表。"""
    designs: list[ExperimentDesign]


class DesignSelection(BaseModel):
    """LLM 推荐的最优方案索引。"""
    selected_index: int
    reasoning: str


# ── 节点函数 ──

def analyze_gaps(
    state: IdeationState, *, llm: BaseChatModel,
) -> dict:
    """LLM 分析 Research Gap。"""
    artifacts = state.get("artifacts", {})
    extraction = artifacts.get("extraction", {})
    notes = extraction.get("reading_notes", [])
    glossary = extraction.get("glossary", {})

    context = json.dumps({
        "reading_notes": notes,
        "glossary": glossary,
    }, ensure_ascii=False)

    result = llm.with_structured_output(GapAnalysisResult).invoke([
        SystemMessage(content=load_prompt(
            "ideation/prompts", key="analyze_gaps",
            variables={"context": ""},
        )["system"]),
        HumanMessage(content=context),
    ])

    logger.info("analyze_gaps_done", gap_count=len(result.gaps))
    return {"research_gaps": result.gaps}


def generate_designs(
    state: IdeationState, *, llm: BaseChatModel,
) -> dict:
    """LLM 针对 Gap 生成实验方案。"""
    gaps = state.get("research_gaps", [])
    artifacts = state.get("artifacts", {})
    supervisor = artifacts.get("supervisor", {})

    context = json.dumps({
        "research_gaps": [g.model_dump() for g in gaps],
        "research_direction": supervisor.get("research_direction", ""),
    }, ensure_ascii=False)

    result = llm.with_structured_output(DesignGenerationResult).invoke([
        SystemMessage(content=load_prompt(
            "ideation/prompts", key="generate_designs",
            variables={"context": ""},
        )["system"]),
        HumanMessage(content=context),
    ])

    logger.info("generate_designs_done", design_count=len(result.designs))
    return {"experiment_designs": result.designs}


def select_design(
    state: IdeationState, *, llm: BaseChatModel,
) -> dict:
    """LLM 推荐排序，选择最优方案。"""
    designs = state.get("experiment_designs", [])
    if not designs:
        logger.info("select_design_skip", reason="no_designs")
        return {"selected_design_index": None}

    context = json.dumps(
        [d.model_dump() for d in designs], ensure_ascii=False,
    )
    result = llm.with_structured_output(DesignSelection).invoke([
        SystemMessage(content=load_prompt(
            "ideation/prompts", key="select_design",
            variables={"context": ""},
        )["system"]),
        HumanMessage(content=context),
    ])

    logger.info(
        "select_design_done",
        selected_index=result.selected_index,
        reasoning=result.reasoning,
    )
    return {"selected_design_index": result.selected_index}


def write_artifacts(state: IdeationState) -> dict:
    """将 Ideation 产出物写入 artifacts 命名空间。"""
    gaps = state.get("research_gaps", [])
    designs = state.get("experiment_designs", [])
    selected = state.get("selected_design_index")

    return {
        "artifacts": {
            "ideation": {
                "research_gaps": [g.model_dump() for g in gaps],
                "experiment_design": (
                    designs[selected].model_dump() if selected is not None and selected < len(designs) else None
                ),
                "all_designs": [d.model_dump() for d in designs],
                "evaluation_metrics": (
                    designs[selected].evaluation_metrics if selected is not None and selected < len(designs) else []
                ),
            },
        },
    }
