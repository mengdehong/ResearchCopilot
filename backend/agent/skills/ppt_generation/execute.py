"""PPT 生成 Skill subgraph 入口。线性流程：plan_outline → confirm_outline → fill_content → render。"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from backend.agent.prompts.loader import load_prompt
from backend.agent.skills.ppt_generation.renderer.base import RenderedPresentation  # noqa: TC001
from backend.agent.skills.ppt_generation.renderer.factory import create_renderer
from backend.agent.skills.ppt_generation.schema import PresentationSchema
from backend.core.logger import get_logger

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

logger = get_logger(__name__)

# 默认路径（可被测试 patch）
TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path("/tmp/ppt_output")


# ── State ──


class PPTGenerationState(TypedDict):
    """PPT 生成 subgraph 私有 state。"""

    content_sections: dict
    scene: str
    template_name: str
    backend: str
    outline_schema: PresentationSchema | None
    full_schema: PresentationSchema | None
    rendered: RenderedPresentation | None


# ── 节点函数 ──


def plan_outline(
    state: PPTGenerationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 从上游产出物提炼大纲级 Schema。"""
    content_sections = state.get("content_sections", {})
    scene = state.get("scene", "paper_presentation")

    context = json.dumps(content_sections, ensure_ascii=False, default=str)
    prompt = load_prompt(
        "ppt_generation/prompts",
        key="plan_outline",
        variables={"scene": scene},
    )

    schema = llm.with_structured_output(PresentationSchema).invoke(
        [
            SystemMessage(content=prompt["system"]),
            HumanMessage(content=context),
        ]
    )

    logger.info("plan_outline_done", slide_count=len(schema.slides))
    return {"outline_schema": schema}


def confirm_outline(state: PPTGenerationState) -> dict:
    """HITL 节点：用户确认或修改大纲。"""
    outline_schema = state.get("outline_schema")
    response = interrupt(
        {
            "action": "confirm_outline",
            "outline": outline_schema.model_dump() if outline_schema else {},
        }
    )

    modified_data = response.get("modified_schema")
    if modified_data:
        modified = PresentationSchema.model_validate(modified_data)
        logger.info("confirm_outline", decision="modified")
        return {"outline_schema": modified}

    logger.info("confirm_outline", decision="approve")
    return {}


def fill_content(
    state: PPTGenerationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """LLM 逐页填充详细内容。"""
    outline_schema = state.get("outline_schema")
    content_sections = state.get("content_sections", {})

    context = json.dumps(
        {
            "outline": outline_schema.model_dump() if outline_schema else {},
            "content_sections": content_sections,
        },
        ensure_ascii=False,
        default=str,
    )

    prompt = load_prompt("ppt_generation/prompts", key="fill_content")

    full_schema = llm.with_structured_output(PresentationSchema).invoke(
        [
            SystemMessage(content=prompt["system"]),
            HumanMessage(content=context),
        ]
    )

    logger.info("fill_content_done", slide_count=len(full_schema.slides))
    return {"full_schema": full_schema}


def render_node(state: PPTGenerationState) -> dict:
    """纯计算节点：调用渲染引擎生成演示文稿。"""
    full_schema = state.get("full_schema")
    if not full_schema:
        logger.warning("render_node_skip", reason="no full_schema")
        return {}

    backend = state.get("backend", "typst")
    template_name = state.get("template_name", "academic_blue")

    # 动态生成隔离的输出目录以防并发冲突
    workspace_id = state.get("workspace_id", "default_workspace")
    import uuid

    run_id = uuid.uuid4().hex[:8]
    output_dir = Path(f"/tmp/research_copilot/{workspace_id}/ppt_{run_id}")

    renderer = create_renderer(backend)
    template_dir = TEMPLATES_DIR / backend / template_name

    result = renderer.render(full_schema, template_dir=template_dir, output_dir=output_dir)
    logger.info(
        "render_done",
        source_type=result.source_type,
        slide_count=result.slide_count,
        pdf_available=result.pdf_path is not None,
    )
    return {"rendered": result}


# ── 图构建 ──


def build_ppt_graph(*, llm: BaseChatModel) -> StateGraph:
    """构建 PPT 生成 subgraph。线性：plan_outline → confirm_outline → fill_content → render。"""
    graph = StateGraph(PPTGenerationState)

    graph.add_node("plan_outline", partial(plan_outline, llm=llm))
    graph.add_node("confirm_outline", confirm_outline)
    graph.add_node("fill_content", partial(fill_content, llm=llm))
    graph.add_node("render", render_node)

    graph.add_edge(START, "plan_outline")
    graph.add_edge("plan_outline", "confirm_outline")
    graph.add_edge("confirm_outline", "fill_content")
    graph.add_edge("fill_content", "render")
    graph.add_edge("render", END)

    return graph
