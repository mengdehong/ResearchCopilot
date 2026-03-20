"""Ideation WF 单元测试。"""
from unittest.mock import MagicMock

from backend.agent.state import ExperimentDesign, ResearchGap
from backend.agent.workflows.ideation.graph import build_ideation_graph
from backend.agent.workflows.ideation.nodes import (
    DesignGenerationResult,
    DesignSelection,
    GapAnalysisResult,
    analyze_gaps,
    generate_designs,
    select_design,
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


# ── analyze_gaps ──

def test_analyze_gaps_returns_gaps() -> None:
    gap = _make_gap()
    llm = _make_mock_llm([GapAnalysisResult(gaps=[gap])])
    state = {"artifacts": {"extraction": {"reading_notes": [], "glossary": {}}}}
    result = analyze_gaps(state, llm=llm)
    assert len(result["research_gaps"]) == 1


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
    }
    result = write_artifacts(state)
    ideation = result["artifacts"]["ideation"]
    assert ideation["experiment_design"] is not None
    assert len(ideation["research_gaps"]) == 1


# ── Subgraph 编译 ──

def test_ideation_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_ideation_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "analyze_gaps" in node_names
    assert "select_design" in node_names
