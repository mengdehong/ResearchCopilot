"""Publish WF 全链路测试。

编译完整的 Publish 子图，端到端验证：
  assemble_outline → generate_markdown → request_finalization (HITL)
  → render_presentation → package_zip → write_artifacts

LLM / interrupt / renderer 使用 mock，验证 Markdown 生成、HITL 定稿和 ZIP 打包。
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.agent.state import OutlineSection
from backend.agent.workflows.publish.graph import build_publish_graph
from backend.agent.workflows.publish.nodes import (
    MarkdownReport,
    OutlineResult,
)


def _build_mock_llm() -> MagicMock:
    """构建 mock LLM：outline + markdown。"""
    responses = [
        # assemble_outline
        OutlineResult(
            sections=[
                OutlineSection(
                    title="Introduction",
                    description="Background and motivation",
                    source_artifacts=["discovery"],
                ),
                OutlineSection(
                    title="Methods",
                    description="Proposed methodology",
                    source_artifacts=["ideation", "execution"],
                ),
            ]
        ),
        # generate_markdown
        MarkdownReport(
            content="# Introduction\n\nThis paper presents...\n\n# Methods\n\nWe propose...",
            citation_map={"[1]": "Paper A, 2024", "[2]": "Paper B, 2023"},
        ),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.asyncio
@patch("backend.agent.workflows.publish.nodes.create_renderer")
@patch("backend.agent.workflows.publish.nodes.interrupt")
async def test_publish_chain_approve(
    mock_interrupt: MagicMock,
    mock_create_renderer: MagicMock,
) -> None:
    """全链路 approve 路径：outline → markdown → HITL approve → render → zip → artifacts。"""
    mock_interrupt.return_value = {}  # approve

    # Mock renderer
    mock_renderer = MagicMock()
    mock_result = MagicMock()
    mock_result.source_path = "/tmp/test.typ"
    mock_result.pdf_path = "/tmp/test.pdf"
    mock_result.slide_count = 2
    mock_result.model_dump.return_value = {
        "source_path": "/tmp/test.typ",
        "pdf_path": "/tmp/test.pdf",
        "slide_count": 2,
    }
    mock_renderer.render.return_value = mock_result
    mock_create_renderer.return_value = mock_renderer

    llm = _build_mock_llm()
    graph = build_publish_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {
            "discovery": {"papers": [{"arxiv_id": "p1", "title": "P1"}]},
            "extraction": {"reading_notes": [{"paper_id": "p1"}]},
            "ideation": {"experiment_design": {"hypothesis": "h1"}},
            "execution": {"results": {"success": True}},
        },
    }

    result = await compiled.ainvoke(input_state)

    # ── 验证 HITL interrupt ──
    mock_interrupt.assert_called_once()

    # ── 验证 artifacts ──
    publish = result["artifacts"]["publish"]
    assert "Introduction" in publish["markdown"]
    assert len(publish["outline"]) == 2
    assert publish["citation_map"]["[1]"] == "Paper A, 2024"
    assert "report.md" in publish["output_files"]
    assert publish["download_key"] is not None
    assert publish["download_key"].startswith("reports/")


@pytest.mark.asyncio
@patch("backend.agent.workflows.publish.nodes.create_renderer")
@patch("backend.agent.workflows.publish.nodes.interrupt")
async def test_publish_chain_reject_with_edit(
    mock_interrupt: MagicMock,
    mock_create_renderer: MagicMock,
) -> None:
    """reject 路径：用户编辑 markdown 后回流 → 使用 modified_markdown。"""
    edited = "# Modified Introduction\n\nUser-edited content."
    mock_interrupt.return_value = {"modified_markdown": edited}

    mock_renderer = MagicMock()
    mock_result = MagicMock()
    mock_result.source_path = None
    mock_result.pdf_path = None
    mock_result.slide_count = 1
    mock_result.model_dump.return_value = {
        "source_path": None,
        "pdf_path": None,
        "slide_count": 1,
    }
    mock_renderer.render.return_value = mock_result
    mock_create_renderer.return_value = mock_renderer

    llm = _build_mock_llm()
    graph = build_publish_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {
            "discovery": {},
            "extraction": {},
            "ideation": {},
        },
    }

    result = await compiled.ainvoke(input_state)

    publish = result["artifacts"]["publish"]
    # markdown 应被替换为用户编辑版本
    assert publish["markdown"] == edited


@pytest.mark.asyncio
@patch("backend.agent.workflows.publish.nodes.create_renderer")
@patch("backend.agent.workflows.publish.nodes.interrupt")
async def test_publish_chain_renderer_fallback(
    mock_interrupt: MagicMock,
    mock_create_renderer: MagicMock,
) -> None:
    """渲染降级：Typst 未安装时优雅降级，ZIP 仍然可用。"""
    mock_interrupt.return_value = {}
    mock_create_renderer.side_effect = RuntimeError("typst not installed")

    llm = _build_mock_llm()
    graph = build_publish_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {"discovery": {}, "extraction": {}, "ideation": {}},
    }

    result = await compiled.ainvoke(input_state)

    publish = result["artifacts"]["publish"]
    # 即使渲染失败，markdown 和 ZIP 仍应存在
    assert publish["markdown"]
    assert publish["download_key"] is not None
    assert "report.md" in publish["output_files"]
    # presentation 应为 None（降级）
    assert publish["presentation"] is None
