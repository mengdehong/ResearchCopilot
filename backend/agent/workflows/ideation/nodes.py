"""Ideation WF 节点函数。三步 CoT 推理：分解问题 → 推理证据 → 合成结论 → 生成方案 → 推荐排序 → 写 artifacts。"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.agent.prompts.loader import load_prompt
from backend.agent.state import ExperimentDesign, IdeationState, ResearchGap
from backend.core.logger import get_logger

logger = get_logger(__name__)


# ── LLM 输出结构 ──


class SubProblem(BaseModel):
    """分解出的子问题。"""

    question: str
    relevant_papers: list[str]
    aspect: str  # methodology / evaluation / application / theory


class DecomposedProblem(BaseModel):
    """LLM 分解问题的结果。"""

    sub_problems: list[SubProblem]
    overall_theme: str


class EvidenceItem(BaseModel):
    """单条证据推理。"""

    sub_question: str
    evidence: list[str]
    reasoning: str
    conclusion: str


class EvidenceReasoning(BaseModel):
    """LLM 证据推理的结果。"""

    items: list[EvidenceItem]


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


# ── CoT Step 1: 分解问题 ──


def decompose_problem(
    state: IdeationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """CoT Step 1: 将上游 extraction 产出分解为可推理的子问题。"""
    artifacts = state.get("artifacts", {})
    extraction = artifacts.get("extraction", {})
    notes = extraction.get("reading_notes", [])
    glossary = extraction.get("glossary", {})

    context_payload: dict = {"reading_notes": notes, "glossary": glossary}

    # Critique 打回时携带修订上下文
    revision_context = state.get("revision_context", "")
    if revision_context:
        context_payload["revision_feedback"] = revision_context

    context = json.dumps(context_payload, ensure_ascii=False)

    result = llm.with_structured_output(DecomposedProblem).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "ideation/prompts",
                    key="decompose_problem",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    cot_trace = list(state.get("cot_trace", []))
    cot_trace.append(
        {
            "step": "decompose_problem",
            "reasoning": result.overall_theme,
            "output": [sp.model_dump() for sp in result.sub_problems],
        }
    )

    logger.info(
        "decompose_problem_done",
        sub_problem_count=len(result.sub_problems),
        theme=result.overall_theme,
    )
    return {"cot_trace": cot_trace}


# ── CoT Step 2: 推理证据 ──


def reason_evidence(
    state: IdeationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """CoT Step 2: 对每个子问题结合证据进行推理。"""
    cot_trace = list(state.get("cot_trace", []))
    decomposition = cot_trace[-1] if cot_trace else {}
    sub_problems = decomposition.get("output", [])

    artifacts = state.get("artifacts", {})
    extraction = artifacts.get("extraction", {})
    notes = extraction.get("reading_notes", [])

    context = json.dumps(
        {"sub_problems": sub_problems, "reading_notes": notes},
        ensure_ascii=False,
    )

    result = llm.with_structured_output(EvidenceReasoning).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "ideation/prompts",
                    key="reason_evidence",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    cot_trace.append(
        {
            "step": "reason_evidence",
            "reasoning": "; ".join(item.reasoning for item in result.items),
            "output": [item.model_dump() for item in result.items],
        }
    )

    logger.info("reason_evidence_done", evidence_count=len(result.items))
    return {"cot_trace": cot_trace}


# ── CoT Step 3: 合成结论 ──


def synthesize_gaps(
    state: IdeationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """CoT Step 3: 综合推理结果得出最终 research gaps。"""
    cot_trace = list(state.get("cot_trace", []))
    evidence_items = cot_trace[-1].get("output", []) if len(cot_trace) >= 2 else []

    context = json.dumps(
        {"evidence_reasoning": evidence_items, "cot_trace": cot_trace},
        ensure_ascii=False,
    )

    result = llm.with_structured_output(GapAnalysisResult).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "ideation/prompts",
                    key="synthesize_gaps",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    cot_trace.append(
        {
            "step": "synthesize_gaps",
            "reasoning": f"Synthesized {len(result.gaps)} research gaps from evidence",
            "output": [g.model_dump() for g in result.gaps],
        }
    )

    logger.info("synthesize_gaps_done", gap_count=len(result.gaps))
    return {"research_gaps": result.gaps, "cot_trace": cot_trace}


# ── 生成实验方案 ──


def generate_designs(
    state: IdeationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 针对 Gap 生成实验方案。"""
    gaps = state.get("research_gaps", [])
    artifacts = state.get("artifacts", {})
    supervisor = artifacts.get("supervisor", {})

    context = json.dumps(
        {
            "research_gaps": [g.model_dump() for g in gaps],
            "research_direction": supervisor.get("research_direction", ""),
        },
        ensure_ascii=False,
    )

    result = llm.with_structured_output(DesignGenerationResult).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "ideation/prompts",
                    key="generate_designs",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    logger.info("generate_designs_done", design_count=len(result.designs))
    return {"experiment_designs": result.designs}


# ── 推荐排序 ──


def select_design(
    state: IdeationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 推荐排序，选择最优方案。"""
    designs = state.get("experiment_designs", [])
    if not designs:
        logger.info("select_design_skip", reason="no_designs")
        return {"selected_design_index": None}

    context = json.dumps(
        [d.model_dump() for d in designs],
        ensure_ascii=False,
    )
    result = llm.with_structured_output(DesignSelection).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "ideation/prompts",
                    key="select_design",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    logger.info(
        "select_design_done",
        selected_index=result.selected_index,
        reasoning=result.reasoning,
    )
    return {"selected_design_index": result.selected_index}


# ── 写 artifacts ──


def write_artifacts(state: IdeationState) -> dict:
    """将 Ideation 产出物写入 artifacts 命名空间。"""
    gaps = state.get("research_gaps", [])
    designs = state.get("experiment_designs", [])
    selected = state.get("selected_design_index")
    cot_trace = state.get("cot_trace", [])

    return {
        "artifacts": {
            "ideation": {
                "research_gaps": [g.model_dump() for g in gaps],
                "experiment_design": (
                    designs[selected].model_dump()
                    if selected is not None and selected < len(designs)
                    else None
                ),
                "all_designs": [d.model_dump() for d in designs],
                "evaluation_metrics": (
                    designs[selected].evaluation_metrics
                    if selected is not None and selected < len(designs)
                    else []
                ),
                "cot_trace": cot_trace,
            },
        },
    }
