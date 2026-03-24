"""Ideation WF 单元测试。"""

from unittest.mock import MagicMock

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
    decompose_problem,
    generate_designs,
    reason_evidence,
    select_design,
    synthesize_gaps,
    write_artifacts,
)


def _make_mock_llm(responses: list) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_gap(**overrides: object) -> ResearchGap:
    defaults = {
        "description": "Gap A",
        "supporting_evidence": ["evidence1"],
        "potential_impact": "high",
    }
    defaults.update(overrides)
    return ResearchGap(**defaults)


def _make_design(**overrides: object) -> ExperimentDesign:
    defaults = {
        "hypothesis": "H1",
        "method_description": "method",
        "baselines": ["baseline1"],
        "datasets": ["dataset1"],
        "evaluation_metrics": ["accuracy"],
        "expected_outcome": "improvement",
    }
    defaults.update(overrides)
    return ExperimentDesign(**defaults)


# ── decompose_problem (CoT Step 1) ──


def test_decompose_problem_returns_cot_trace() -> None:
    sub = SubProblem(
        question="How to improve X?",
        relevant_papers=["p1"],
        aspect="methodology",
    )
    llm = _make_mock_llm(
        [
            DecomposedProblem(sub_problems=[sub], overall_theme="AI optimization"),
        ]
    )
    state = {"artifacts": {"extraction": {"reading_notes": [], "glossary": {}}}}
    result = decompose_problem(state, llm=llm)
    assert len(result["cot_trace"]) == 1
    assert result["cot_trace"][0]["step"] == "decompose_problem"
    assert len(result["cot_trace"][0]["output"]) == 1


# ── reason_evidence (CoT Step 2) ──


def test_reason_evidence_appends_to_trace() -> None:
    item = EvidenceItem(
        sub_question="Q1",
        evidence=["e1"],
        reasoning="because X",
        conclusion="therefore Y",
    )
    llm = _make_mock_llm([EvidenceReasoning(items=[item])])
    state = {
        "cot_trace": [{"step": "decompose_problem", "reasoning": "theme", "output": []}],
        "artifacts": {"extraction": {"reading_notes": []}},
    }
    result = reason_evidence(state, llm=llm)
    assert len(result["cot_trace"]) == 2
    assert result["cot_trace"][1]["step"] == "reason_evidence"


# ── synthesize_gaps (CoT Step 3) ──


def test_synthesize_gaps_produces_gaps() -> None:
    gap = _make_gap()
    llm = _make_mock_llm([GapAnalysisResult(gaps=[gap])])
    state = {
        "cot_trace": [
            {"step": "decompose_problem", "reasoning": "", "output": []},
            {"step": "reason_evidence", "reasoning": "", "output": []},
        ],
    }
    result = synthesize_gaps(state, llm=llm)
    assert len(result["research_gaps"]) == 1
    assert len(result["cot_trace"]) == 3
    assert result["cot_trace"][2]["step"] == "synthesize_gaps"


# ── generate_designs ──


def test_generate_designs_returns_designs() -> None:
    design = _make_design()
    llm = _make_mock_llm([DesignGenerationResult(designs=[design])])
    state = {
        "research_gaps": [_make_gap()],
        "artifacts": {"supervisor": {"research_direction": "test"}},
    }
    result = generate_designs(state, llm=llm)
    assert len(result["experiment_designs"]) == 1


# ── select_design ──


def test_select_design_returns_index() -> None:
    llm = _make_mock_llm([DesignSelection(selected_index=0, reasoning="best")])
    state = {"experiment_designs": [_make_design()]}
    result = select_design(state, llm=llm)
    assert result["selected_design_index"] == 0


def test_select_design_no_designs() -> None:
    state = {"experiment_designs": []}
    result = select_design(state, llm=MagicMock())
    assert result["selected_design_index"] is None


# ── write_artifacts ──


def test_ideation_write_artifacts() -> None:
    design = _make_design()
    state = {
        "research_gaps": [_make_gap()],
        "experiment_designs": [design],
        "selected_design_index": 0,
        "cot_trace": [{"step": "test", "reasoning": "r", "output": []}],
    }
    result = write_artifacts(state)
    ideation = result["artifacts"]["ideation"]
    assert ideation["experiment_design"] is not None
    assert len(ideation["research_gaps"]) == 1
    assert len(ideation["cot_trace"]) == 1


# ── Subgraph 编译 ──


def test_ideation_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_ideation_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "decompose_problem" in node_names
    assert "reason_evidence" in node_names
    assert "synthesize_gaps" in node_names
    assert "generate_designs" in node_names
    assert "select_design" in node_names
