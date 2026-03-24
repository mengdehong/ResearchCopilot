"""Publish WF 节点函数。报告交付：大纲组装 → Markdown 生成 → HITL 定稿 → 渲染 → 打包 → 写 artifacts。"""

import io
import json
import zipfile
from pathlib import Path
from uuid import uuid4

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
UPLOADS_DIR = Path("/tmp/research-copilot-uploads")


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
    """渲染演示文稿。支持 Typst 和 Beamer 后端。"""
    markdown = state.get("markdown_content", "")
    output_files = list(state.get("output_files", []))
    render_backend = state.get("render_backend", "typst")

    if markdown:
        output_files.append("report.md")

    # 构建简化 PresentationSchema 用于渲染
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

    # 根据 render_backend 选择渲染器
    try:
        renderer = create_renderer(render_backend)
        if render_backend == "typst":
            template_dir = TEMPLATES_DIR / "typst" / "academic_blue"
        else:
            template_dir = TEMPLATES_DIR / "beamer" / "metropolis"
        result = renderer.render(schema, template_dir=template_dir, output_dir=PPT_OUTPUT_DIR)

        if result.source_path:
            source_ext = "presentation.typ" if render_backend == "typst" else "presentation.tex"
            output_files.append(source_ext)
        if result.pdf_path:
            output_files.append("presentation.pdf")

        logger.info(
            "render_presentation",
            status=render_backend,
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


# ── ZIP 打包辅助函数 ──


def _collect_literature_pdfs(
    artifacts: dict,
) -> list[tuple[str, Path]]:
    """从 discovery artifacts 收集已下载的论文 PDF 路径。

    返回 (zip_内部路径, 本地文件路径) 列表。
    """
    discovery = artifacts.get("discovery", {})
    ingestion_ids = discovery.get("ingestion_task_ids", [])
    all_selected = list(discovery.get("selected_paper_ids", []))

    files: list[tuple[str, Path]] = []
    for arxiv_id, doc_id in zip(all_selected, ingestion_ids, strict=False):
        if doc_id.startswith("failed_"):
            continue
        # 查找本地存储的 PDF 文件
        pdf_path = UPLOADS_DIR / "documents" / f"{doc_id}.pdf"
        if pdf_path.exists():
            safe_name = arxiv_id.replace("/", "_")
            files.append((f"literature/{safe_name}.pdf", pdf_path))

    return files


def _collect_execution_outputs(
    artifacts: dict,
) -> list[tuple[str, Path]]:
    """从 execution artifacts 收集沙箱产出的代码和图表文件。

    返回 (zip_内部路径, 本地文件路径) 列表。
    """
    execution = artifacts.get("execution", {})
    output_files = execution.get("output_files", [])

    files: list[tuple[str, Path]] = []
    for file_path_str in output_files:
        local_path = Path(file_path_str)
        if not local_path.exists():
            # 尝试在 sandbox 输出目录中查找
            sandbox_path = Path("/tmp/sandbox_output") / local_path.name
            if sandbox_path.exists():
                local_path = sandbox_path
            else:
                continue

        # 按文件类型分目录
        ext = local_path.suffix.lower()
        if ext in (".py", ".r", ".jl", ".ipynb", ".sh"):
            zip_dir = "code"
        elif ext in (".png", ".jpg", ".jpeg", ".svg", ".pdf", ".html"):
            zip_dir = "charts"
        else:
            zip_dir = "code"

        files.append((f"{zip_dir}/{local_path.name}", local_path))

    return files


def _collect_presentation_files() -> list[tuple[str, Path]]:
    """收集渲染产出的演示文件。

    返回 (zip_内部路径, 本地文件路径) 列表。
    """
    files: list[tuple[str, Path]] = []
    for ext in ("typ", "tex", "pdf"):
        path = PPT_OUTPUT_DIR / f"presentation.{ext}"
        if path.exists():
            files.append((f"slides/presentation.{ext}", path))
    return files


def package_zip(state: PublishState) -> dict:
    """将产出文件打包为 ZIP 并持久化到本地存储。

    ZIP 包含：
    - /report.md + citations.json  (报告和引用)
    - /slides/                     (演示文稿 PDF/源文件)
    - /literature/                 (论文 PDF 文件)
    - /code/                       (沙箱产出代码)
    - /charts/                     (沙箱产出图表)
    """
    markdown = state.get("markdown_content", "")
    output_files = list(state.get("output_files", []))
    citation_map = state.get("citation_map", {})
    artifacts = state.get("artifacts", {})

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. 报告和引用
        if markdown:
            zf.writestr("report.md", markdown)
            if "report.md" not in output_files:
                output_files.append("report.md")
        if citation_map:
            zf.writestr("citations.json", json.dumps(citation_map, ensure_ascii=False, indent=2))
            if "citations.json" not in output_files:
                output_files.append("citations.json")

        # 2. 演示文稿文件
        for zip_path, local_path in _collect_presentation_files():
            zf.write(local_path, zip_path)
            if zip_path not in output_files:
                output_files.append(zip_path)

        # 3. 论文 PDF 文件
        for zip_path, local_path in _collect_literature_pdfs(artifacts):
            zf.write(local_path, zip_path)
            if zip_path not in output_files:
                output_files.append(zip_path)

        # 4. 沙箱产出（代码和图表）
        for zip_path, local_path in _collect_execution_outputs(artifacts):
            zf.write(local_path, zip_path)
            if zip_path not in output_files:
                output_files.append(zip_path)

    zip_bytes = buf.getvalue()

    # 持久化到本地存储
    workspace_id = state.get("workspace_id", "default")
    download_key = f"reports/{workspace_id}/{uuid4().hex}.zip"
    target = UPLOADS_DIR / download_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zip_bytes)

    logger.info(
        "package_zip_done",
        file_count=len(output_files),
        zip_size=len(zip_bytes),
        download_key=download_key,
    )
    return {"output_files": output_files, "zip_bytes": zip_bytes, "download_key": download_key}


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
                "download_key": state.get("download_key"),
            },
        },
    }
