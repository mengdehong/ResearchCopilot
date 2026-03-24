"""Ideation WF 全链路测试。

编译完整的 Ideation 子图，端到端验证：
  analyze_gaps → generate_designs → select_design → write_artifacts

LLM 使用 mock，验证 gaps → designs → selected_design 数据流和最终 artifacts 结构。
"""

from unittest.mock import MagicMock

import pytest

from backend.agent.state import ExperimentDesign, ResearchGap
from backend.agent.workflows.ideation.graph import build_ideation_graph
from backend.agent.workflows.ideation.nodes import (
    DesignGenerationResult,
    DesignSelection,
    GapAnalysisResult,
)


def _build_mock_llm() -> MagicMock:
    """构建 mock LLM，按 3 节点调用顺序返回。

    调用顺序：analyze_gaps → generate_designs → select_design
    """
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
        # analyze_gaps
        GapAnalysisResult(gaps=[gap]),
        # generate_designs
        DesignGenerationResult(designs=[design]),
        # select_design
        DesignSelection(selected_index=0, reasoning="Only viable approach for NISQ"),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.asyncio
async def test_ideation_chain_full() -> None:
    """全链路：analyze_gaps → generate_designs → select_design → artifacts。

    验证：
    1. analyze_gaps 产生 research_gaps
    2. generate_designs 生成实验方案
    3. select_design 选择最优方案
    4. write_artifacts 输出含 gaps, designs, selected_design
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

    # ── 验证 LLM 被调用 3 次 ──
    structured = llm.with_structured_output.return_value
    assert structured.invoke.call_count == 3

    # ── 验证 artifacts ──
    ideation = result["artifacts"]["ideation"]

    # research_gaps
    assert len(ideation["research_gaps"]) == 1
    assert "quantum" in ideation["research_gaps"][0]["description"].lower()

    # experiment_design (selected)
    assert ideation["experiment_design"] is not None
    assert "surface code" in ideation["experiment_design"]["hypothesis"].lower()

    # all_designs
    assert len(ideation["all_designs"]) == 1

    # evaluation_metrics
    assert len(ideation["evaluation_metrics"]) == 2


@pytest.mark.asyncio
async def test_ideation_chain_no_designs() -> None:
    """降级场景：generate_designs 返回空列表 → selected_design_index = None。"""
    gap = ResearchGap(
        description="Gap",
        supporting_evidence=["e1"],
        potential_impact="impact",
    )
    responses = [
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
    # LLM 只被调用 2 次（analyze_gaps + generate_designs），select_design 跳过
    assert structured.invoke.call_count == 2
