"""Publish WF 单元测试。"""
from unittest.mock import MagicMock, patch

from backend.agent.state import OutlineSection
from backend.agent.workflows.publish.graph import build_publish_graph
from backend.agent.workflows.publish.nodes import (
    MarkdownReport,
    OutlineResult,
    assemble_outline,
    generate_markdown,
    package_zip,
    render_presentation,
    request_finalization,
    write_artifacts,
)


def _make_mock_llm(responses: list) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_section(**overrides: object) -> OutlineSection:
    defaults = {
        "title": "Introduction",
        "description": "intro content",
        "source_artifacts": ["extraction.reading_notes"],
    }
    defaults.update(overrides)
    return OutlineSection(**defaults)


# ── assemble_outline ──

def test_assemble_outline_returns_sections() -> None:
    section = _make_section()
    llm = _make_mock_llm([OutlineResult(sections=[section])])
    state = {"artifacts": {"extraction": {"notes": "data"}}}
    result = assemble_outline(state, llm=llm)
    assert len(result["outline"]) == 1


# ── generate_markdown ──

def test_generate_markdown_returns_content() -> None:
    llm = _make_mock_llm([
        MarkdownReport(content="# Report\ncontent", citation_map={"1": "paper1"}),
    ])
    state = {
        "outline": [_make_section()],
        "artifacts": {"extraction": {}, "ideation": {}, "execution": {}},
    }
    result = generate_markdown(state, llm=llm)
    assert "Report" in result["markdown_content"]
    assert "1" in result["citation_map"]


# ── request_finalization (HITL) ──

def test_request_finalization_approve() -> None:
    state = {"markdown_content": "# Report", "outline": [_make_section()]}
    with patch(
        "backend.agent.workflows.publish.nodes.interrupt",
        return_value={"decision": "approve"},
    ):
        result = request_finalization(state)
    assert result == {}


def test_request_finalization_reject_with_edit() -> None:
    state = {"markdown_content": "# Report", "outline": [_make_section()]}
    with patch(
        "backend.agent.workflows.publish.nodes.interrupt",
        return_value={"modified_markdown": "# Edited Report"},
    ):
        result = request_finalization(state)
    assert result["markdown_content"] == "# Edited Report"


# ── render_presentation ──

def test_render_presentation_placeholder() -> None:
    state = {"output_files": ["existing.pdf"]}
    result = render_presentation(state)
    assert result["output_files"] == ["existing.pdf"]


# ── package_zip ──

def test_package_zip_adds_report() -> None:
    state = {"markdown_content": "# Report", "output_files": []}
    result = package_zip(state)
    assert "report.md" in result["output_files"]


# ── write_artifacts ──

def test_publish_write_artifacts() -> None:
    state = {
        "markdown_content": "# Report",
        "outline": [_make_section()],
        "citation_map": {"1": "p1"},
        "output_files": ["report.md"],
    }
    result = write_artifacts(state)
    publish = result["artifacts"]["publish"]
    assert publish["markdown"] == "# Report"
    assert len(publish["outline"]) == 1


# ── Subgraph 编译 ──

def test_publish_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_publish_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "assemble_outline" in node_names
    assert "request_finalization" in node_names
    assert "write_artifacts" in node_names
