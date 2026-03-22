"""Publish WF 节点函数。报告交付：大纲组装 → Markdown 生成 → HITL 定稿 → 渲染 → 打包 → 写 artifacts。"""

import io
import json
import zipfile
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel

from backend.agent.prompts.loader import load_prompt
from backend.agent.skills.ppt_generation.renderer.factory import create_renderer
from backend.agent.skills.ppt_generation.schema import (
    BulletsContent,
    PresentationMeta,
    PresentationSchema,
    SlideSchema,
)
from backend.agent.state import OutlineSection, PublishState
from backend.core.logger import get_logger

logger = get_logger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "skills/ppt_generation/templates"
PPT_OUTPUT_DIR = Path("/tmp/ppt_output")


# ── LLM 输出结构 ──


class OutlineResult(BaseModel):
    """LLM 生成的报告大纲。"""

    sections: list[OutlineSection]


class MarkdownReport(BaseModel):
    """LLM 生成的 Markdown 报告。"""

    content: str
    citation_map: dict[str, str]


# ── 节点函数 ──


def assemble_outline(
    state: PublishState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 从 artifacts 组装报告大纲。"""
    artifacts = state.get("artifacts", {})
    context = json.dumps(
        {
            k: v
            for k, v in artifacts.items()
            if k in ("discovery", "extraction", "ideation", "execution", "critique")
        },
        ensure_ascii=False,
        default=str,
    )

    result = llm.with_structured_output(OutlineResult).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "publish/prompts",
                    key="assemble_outline",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    logger.info("assemble_outline_done", section_count=len(result.sections))
    return {"outline": result.sections}


def generate_markdown(
    state: PublishState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 根据大纲和 artifacts 生成完整 Markdown 报告。"""
    outline = state.get("outline", [])
    artifacts = state.get("artifacts", {})

    context = json.dumps(
        {
            "outline": [s.model_dump() for s in outline],
            "artifacts": {
                k: v for k, v in artifacts.items() if k in ("extraction", "ideation", "execution")
            },
        },
        ensure_ascii=False,
        default=str,
    )

    result = llm.with_structured_output(MarkdownReport).invoke(
        [
            SystemMessage(
                content=load_prompt(
                    "publish/prompts",
                    key="generate_markdown",
                    variables={"context": ""},
                )["system"]
            ),
            HumanMessage(content=context),
        ]
    )

    logger.info("generate_markdown_done", content_length=len(result.content))
    return {
        "markdown_content": result.content,
        "citation_map": result.citation_map,
    }


def request_finalization(state: PublishState) -> dict:
    """独立 HITL 节点：展示 Markdown 报告，用户可 approve 或 reject。

    reject 时 Markdown 推送至 Canvas，用户手改完确认后回流 modified_markdown。
    """
    response = interrupt(
        {
            "action": "confirm_finalize",
            "markdown_preview": state.get("markdown_content", "")[:2000],
            "outline": [s.title for s in state.get("outline", [])],
        }
    )
    if not isinstance(response, dict):
        response = {}

    # approve: {} 或 {"decision": "approve"}
    # reject→Canvas→手改→回流: {"modified_markdown": "..."}
    modified = response.get("modified_markdown")
    if modified:
        logger.info("request_finalization", decision="reject_with_edit")
        return {"markdown_content": modified, "user_edited_markdown": modified}

    logger.info("request_finalization", decision="approve")
    return {}


def render_presentation(state: PublishState) -> dict:
    """渲染演示文稿。从 Markdown 报告内容构建 PresentationSchema 并通过 Typst 渲染。"""
    markdown = state.get("markdown_content", "")
    output_files = list(state.get("output_files", []))

    if markdown:
        output_files.append("report.md")

    # 构建简化 PresentationSchema 用于 PPT 渲染
    outline = state.get("outline", [])
    slides = [
        SlideSchema(
            id=f"s{i}",
            layout="bullets",
            section=section.title,
            content=BulletsContent(
                heading=section.title,
                points=[section.description],
            ),
        )
        for i, section in enumerate(outline)
    ]
    schema = PresentationSchema(
        meta=PresentationMeta(
            scene="paper_presentation",
            title=outline[0].title if outline else "Research Report",
            authors=["Research Copilot"],
        ),
        slides=slides,
    )

    # 渲染（Typst 未安装时优雅降级）
    try:
        renderer = create_renderer("typst")
        template_dir = TEMPLATES_DIR / "typst" / "academic_blue"
        result = renderer.render(schema, template_dir=template_dir, output_dir=PPT_OUTPUT_DIR)

        if result.source_path:
            output_files.append("presentation.typ")
        if result.pdf_path:
            output_files.append("presentation.pdf")

        logger.info(
            "render_presentation",
            status="typst",
            slide_count=result.slide_count,
            pdf_available=result.pdf_path is not None,
        )
        return {
            "output_files": output_files,
            "presentation_schema": schema.model_dump(),
            "rendered_presentation": result.model_dump(),
        }
    except Exception as exc:
        logger.warning("render_presentation_fallback", error=str(exc))
        return {
            "output_files": output_files,
            "presentation_schema": schema.model_dump(),
            "rendered_presentation": None,
        }


def package_zip(state: PublishState) -> dict:
    """将产出文件打包为 ZIP。"""
    markdown = state.get("markdown_content", "")
    output_files = list(state.get("output_files", []))
    citation_map = state.get("citation_map", {})

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if markdown:
            zf.writestr("report.md", markdown)
            if "report.md" not in output_files:
                output_files.append("report.md")
        if citation_map:
            zf.writestr("citations.json", json.dumps(citation_map, ensure_ascii=False, indent=2))
            if "citations.json" not in output_files:
                output_files.append("citations.json")

    zip_bytes = buf.getvalue()
    logger.info("package_zip_done", file_count=len(output_files), zip_size=len(zip_bytes))
    return {"output_files": output_files, "zip_bytes": zip_bytes}


def write_artifacts(state: PublishState) -> dict:
    """将 Publish 产出物写入 artifacts 命名空间。"""
    return {
        "artifacts": {
            "publish": {
                "markdown": state.get("markdown_content", ""),
                "outline": [s.model_dump() for s in state.get("outline", [])],
                "citation_map": state.get("citation_map", {}),
                "output_files": state.get("output_files", []),
                "presentation": state.get("rendered_presentation"),
            },
        },
    }
