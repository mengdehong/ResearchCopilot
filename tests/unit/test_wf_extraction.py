"""Extraction WF 单元测试。"""
from unittest.mock import MagicMock

from backend.agent.state import ComparisonEntry, ReadingNote
from backend.agent.workflows.extraction.graph import build_extraction_graph
from backend.agent.workflows.extraction.nodes import (
    ComparisonResult,
    GeneratedNote,
    GlossaryResult,
    build_glossary,
    check_existing_notes,
    cross_compare,
    generate_notes,
    wait_rag_ready,
    write_artifacts,
)


def _make_mock_llm(responses: list) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_reading_note(**overrides: object) -> ReadingNote:
    defaults = {
        "paper_id": "p1",
        "key_contributions": ["contrib1"],
        "methodology": "method1",
        "experimental_setup": "setup1",
        "main_results": "results1",
        "limitations": ["lim1"],
        "source_chunks": [],
    }
    defaults.update(overrides)
    return ReadingNote(**defaults)


# ── wait_rag_ready ──

def test_wait_rag_ready_extracts_paper_ids() -> None:
    state = {"artifacts": {"discovery": {"selected_paper_ids": ["p1", "p2"]}}}
    result = wait_rag_ready(state)
    assert result["paper_ids"] == ["p1", "p2"]


def test_wait_rag_ready_empty_artifacts() -> None:
    state = {"artifacts": {}}
    result = wait_rag_ready(state)
    assert result["paper_ids"] == []


# ── check_existing_notes ──

def test_check_existing_notes_skips_existing() -> None:
    state = {
        "paper_ids": ["p1", "p2", "p3"],
        "reading_notes": [_make_reading_note(paper_id="p1")],
    }
    result = check_existing_notes(state)
    assert result["paper_ids"] == ["p2", "p3"]


# ── generate_notes ──

def test_generate_notes_creates_notes() -> None:
    llm = _make_mock_llm([
        GeneratedNote(
            key_contributions=["c1"], methodology="m1",
            experimental_setup="s1", main_results="r1", limitations=["l1"],
        ),
    ])
    state = {
        "paper_ids": ["p1"],
        "reading_notes": [],
        "artifacts": {"discovery": {"papers": [{"arxiv_id": "p1", "title": "T", "abstract": "A"}]}},
    }
    result = generate_notes(state, llm=llm)
    assert len(result["reading_notes"]) == 1
    assert result["reading_notes"][0].paper_id == "p1"


# ── cross_compare ──

def test_cross_compare_skips_single_paper() -> None:
    state = {"reading_notes": [_make_reading_note()]}
    result = cross_compare(state, llm=MagicMock())
    assert result["comparison_matrix"] == []


def test_cross_compare_produces_entries() -> None:
    llm = _make_mock_llm([
        ComparisonResult(entries=[
            ComparisonEntry(
                paper_id="p1", method="m", dataset="d",
                metric_values={"acc": 0.9}, key_difference="diff",
            ),
        ]),
    ])
    state = {
        "reading_notes": [
            _make_reading_note(paper_id="p1"),
            _make_reading_note(paper_id="p2"),
        ],
    }
    result = cross_compare(state, llm=llm)
    assert len(result["comparison_matrix"]) == 1


# ── build_glossary ──

def test_build_glossary_returns_terms() -> None:
    llm = _make_mock_llm([
        GlossaryResult(terms={"term1": "definition1"}),
    ])
    state = {"reading_notes": [_make_reading_note()]}
    result = build_glossary(state, llm=llm)
    assert "term1" in result["glossary"]


# ── write_artifacts ──

def test_extraction_write_artifacts() -> None:
    state = {
        "reading_notes": [_make_reading_note()],
        "comparison_matrix": [],
        "glossary": {"k": "v"},
    }
    result = write_artifacts(state)
    extraction = result["artifacts"]["extraction"]
    assert len(extraction["reading_notes"]) == 1
    assert extraction["glossary"] == {"k": "v"}


# ── Subgraph 编译 ──

def test_extraction_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_extraction_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "wait_rag_ready" in node_names
    assert "generate_notes" in node_names
    assert "write_artifacts" in node_names
