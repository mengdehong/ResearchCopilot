"""Publish WF 节点函数。报告交付：大纲组装 → Markdown 生成 → HITL 定稿 → 渲染 → 打包 → 写 artifacts。"""
import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel

from backend.agent.prompts.loader import load_prompt
from backend.agent.state import OutlineSection, PublishState
from backend.core.logger import get_logger

logger = get_logger(__name__)


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
    state: PublishState, *, llm: BaseChatModel,
) -> dict:
    """LLM 从 artifacts 组装报告大纲。"""
    artifacts = state.get("artifacts", {})
    context = json.dumps({
        k: v for k, v in artifacts.items()
        if k in ("discovery", "extraction", "ideation", "execution", "critique")
    }, ensure_ascii=False, default=str)

    result = llm.with_structured_output(OutlineResult).invoke([
        SystemMessage(content=load_prompt(
            "publish/prompts", key="assemble_outline",
            variables={"context": ""},
        )["system"]),
        HumanMessage(content=context),
    ])

    logger.info("assemble_outline_done", section_count=len(result.sections))
    return {"outline": result.sections}


def generate_markdown(
    state: PublishState, *, llm: BaseChatModel,
) -> dict:
    """LLM 根据大纲和 artifacts 生成完整 Markdown 报告。"""
    outline = state.get("outline", [])
    artifacts = state.get("artifacts", {})

    context = json.dumps({
        "outline": [s.model_dump() for s in outline],
        "artifacts": {
            k: v for k, v in artifacts.items()
            if k in ("extraction", "ideation", "execution")
        },
    }, ensure_ascii=False, default=str)

    result = llm.with_structured_output(MarkdownReport).invoke([
        SystemMessage(content=load_prompt(
            "publish/prompts", key="generate_markdown",
            variables={"context": ""},
        )["system"]),
        HumanMessage(content=context),
    ])

    logger.info("generate_markdown_done", content_length=len(result.content))
    return {
        "markdown_content": result.content,
        "citation_map": result.citation_map,
    }


def request_finalization(state: PublishState) -> dict:
    """独立 HITL 节点：展示 Markdown 报告，用户可 approve 或 reject。

    reject 时 Markdown 推送至 Canvas，用户手改完确认后回流 modified_markdown。
    """
    response = interrupt({
        "action": "confirm_finalize",
        "markdown_preview": state.get("markdown_content", "")[:2000],
        "outline": [s.title for s in state.get("outline", [])],
    })

    # approve: {} 或 {"decision": "approve"}
    # reject→Canvas→手改→回流: {"modified_markdown": "..."}
    modified = response.get("modified_markdown")
    if modified:
        logger.info("request_finalization", decision="reject_with_edit")
        return {"markdown_content": modified, "user_edited_markdown": modified}

    logger.info("request_finalization", decision="approve")
    return {}


def render_presentation(state: PublishState) -> dict:
    """渲染演示文稿。

    当前为占位实现。后续 Phase 7 接入 Typst/Beamer 渲染。
    """
    # TODO(phase-7): 接入 ppt_generation Skill（Typst 主推）
    logger.info("render_presentation", status="placeholder")
    return {"output_files": state.get("output_files", [])}


def package_zip(state: PublishState) -> dict:
    """将产出文件打包为 ZIP。

    当前为占位实现，记录文件列表。
    """
    markdown = state.get("markdown_content", "")
    output_files = list(state.get("output_files", []))

    if markdown:
        output_files.append("report.md")

    # TODO(phase-7): 真实 ZIP 打包
    logger.info("package_zip_done", file_count=len(output_files))
    return {"output_files": output_files}


def write_artifacts(state: PublishState) -> dict:
    """将 Publish 产出物写入 artifacts 命名空间。"""
    return {
        "artifacts": {
            "publish": {
                "markdown": state.get("markdown_content", ""),
                "outline": [s.model_dump() for s in state.get("outline", [])],
                "citation_map": state.get("citation_map", {}),
                "output_files": state.get("output_files", []),
            },
        },
    }
