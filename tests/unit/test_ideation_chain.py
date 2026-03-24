"""Ideation WF 全链路测试。

编译完整的 Ideation 子图，端到端验证：
  decompose_problem → reason_evidence → synthesize_gaps
  → generate_designs → select_design → write_artifacts

LLM 使用 mock，验证三步 CoT 数据流和最终 artifacts 结构。
"""

from unittest.mock import MagicMock

import pytest

from backend.agent.state import ExperimentDesign, ResearchGap
from backend.agent.workflows.ideation.graph import build_ideation_graph
from backend.agent.workflows.ideation.nodes import (
    DecomposedProblem,
    DesignGenerationResult,
    DesignSelection,
    EvidenceItem,
    EvidenceReasoning,
    GapAnalysisResult,
    SubProblem,
)


def _build_mock_llm() -> MagicMock:
    """构建 mock LLM，按 5 节点调用顺序返回。

    调用顺序：
    1. decompose_problem  → DecomposedProblem
    2. reason_evidence    → EvidenceReasoning
    3. synthesize_gaps    → GapAnalysisResult
    4. generate_designs   → DesignGenerationResult
    5. select_design      → DesignSelection
    """
    sub_problem = SubProblem(
        question="How to reduce quantum error rates on NISQ devices?",
        relevant_papers=["p1", "p2"],
        aspect="methodology",
    )
    evidence_item = EvidenceItem(
        sub_question="How to reduce quantum error rates on NISQ devices?",
        evidence=["Surface code shows promise", "NISQ devices have high error rates"],
        reasoning="Surface code variants can reduce overhead",
        conclusion="Surface code variants are viable for NISQ",
    )
    gap = ResearchGap(
        description="No efficient quantum error correction for NISQ",
        supporting_evidence=["Evidence from paper p1"],
        potential_impact="High impact on near-term quantum advantage",
    )
    design = ExperimentDesign(
        hypothesis="Surface code variants can reduce overhead by 30%",
        method_description="Compare surface code variants on NISQ simulators",
        baselines=["Standard surface code", "Repetition code"],
        datasets=["IBM quantum simulator", "Google Sycamore traces"],
        evaluation_metrics=["logical error rate", "qubit overhead"],
        expected_outcome="30% reduction in qubit overhead",
    )

    responses = [
        # 1. decompose_problem
        DecomposedProblem(
            sub_problems=[sub_problem],
            overall_theme="Quantum error correction efficiency on NISQ devices",
        ),
        # 2. reason_evidence
        EvidenceReasoning(items=[evidence_item]),
        # 3. synthesize_gaps
        GapAnalysisResult(gaps=[gap]),
        # 4. generate_designs
        DesignGenerationResult(designs=[design]),
        # 5. select_design
        DesignSelection(selected_index=0, reasoning="Only viable approach for NISQ"),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.asyncio
async def test_ideation_chain_full() -> None:
    """全链路：decompose → reason → synthesize → generate → select → artifacts。

    验证：
    1. 三步 CoT 各产出正确数据结构
    2. synthesize_gaps 产生 research_gaps
    3. generate_designs 生成实验方案
    4. select_design 选择最优方案
    5. write_artifacts 输出含 gaps, designs, selected_design, cot_trace
    """
    llm = _build_mock_llm()
    graph = build_ideation_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {
            "extraction": {
                "reading_notes": [
                    {"paper_id": "p1", "key_contributions": ["QEC survey"]},
                    {"paper_id": "p2", "key_contributions": ["NISQ limits"]},
                ],
                "glossary": {"NISQ": "Noisy Intermediate-Scale Quantum"},
            },
        },
    }

    result = await compiled.ainvoke(input_state)

    # ── 验证 LLM 被调用 5 次 ──
    structured = llm.with_structured_output.return_value
    assert structured.invoke.call_count == 5

    # ── 验证 cot_trace 含 3 步 CoT ──
    ideation = result["artifacts"]["ideation"]
    cot_trace = ideation["cot_trace"]
    cot_steps = [entry["step"] for entry in cot_trace]
    assert "decompose_problem" in cot_steps
    assert "reason_evidence" in cot_steps
    assert "synthesize_gaps" in cot_steps

    # ── 验证 research_gaps ──
    assert len(ideation["research_gaps"]) == 1
    assert "quantum" in ideation["research_gaps"][0]["description"].lower()

    # ── 验证 experiment_design (selected) ──
    assert ideation["experiment_design"] is not None
    assert "surface code" in ideation["experiment_design"]["hypothesis"].lower()

    # ── 验证 all_designs ──
    assert len(ideation["all_designs"]) == 1

    # ── 验证 evaluation_metrics ──
    assert len(ideation["evaluation_metrics"]) == 2


@pytest.mark.asyncio
async def test_ideation_chain_no_designs() -> None:
    """降级场景：generate_designs 返回空列表 → selected_design_index = None。"""
    sub_problem = SubProblem(
        question="Gap question",
        relevant_papers=["p1"],
        aspect="theory",
    )
    evidence_item = EvidenceItem(
        sub_question="Gap question",
        evidence=["e1"],
        reasoning="reasoning",
        conclusion="conclusion",
    )
    gap = ResearchGap(
        description="Gap",
        supporting_evidence=["e1"],
        potential_impact="impact",
    )
    responses = [
        DecomposedProblem(
            sub_problems=[sub_problem],
            overall_theme="General theme",
        ),
        EvidenceReasoning(items=[evidence_item]),
        GapAnalysisResult(gaps=[gap]),
        DesignGenerationResult(designs=[]),  # 空！
        # select_design 在 designs 为空时跳过 LLM 调用
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)

    graph = build_ideation_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {"extraction": {"reading_notes": [], "glossary": {}}},
    }

    result = await compiled.ainvoke(input_state)

    ideation = result["artifacts"]["ideation"]
    assert ideation["experiment_design"] is None
    assert ideation["all_designs"] == []
    # LLM 只被调用 4 次（decompose + reason + synthesize + generate），select_design 跳过
    assert structured.invoke.call_count == 4
