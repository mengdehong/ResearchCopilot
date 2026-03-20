"""Slide Schema 数据模型。LLM 生成此 Schema，渲染层消费它。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# ── 引用 ──


class Reference(BaseModel):
    """学术引用条目。"""

    key: str
    text: str


# ── 元信息 ──


class PresentationMeta(BaseModel):
    """演示文稿元信息。"""

    scene: Literal["paper_presentation", "literature_review"]
    title: str
    subtitle: str | None = None
    authors: list[str]
    presenter: str | None = None
    date: str | None = None
    language: str = "zh"
    template_version: str | None = None
    references: list[Reference] = []


# ── 9 种版式 Content ──


class TitleContent(BaseModel):
    """标题页 — 从 Meta 自动填充。"""


class OutlineContent(BaseModel):
    """目录页 — 从 slides[].section 自动生成。"""

    active_index: int | None = None


class BulletsContent(BaseModel):
    """要点页。"""

    heading: str
    points: list[str]
    note: str | None = None


class FormulaContent(BaseModel):
    """公式页。"""

    heading: str
    formula: str
    explanation: list[str]


class FigureContent(BaseModel):
    """图文页。"""

    heading: str
    image_ref: str
    caption: str
    points: list[str]
    layout: Literal["left_img", "right_img"] = "left_img"


class TableContent(BaseModel):
    """表格对比页。"""

    heading: str
    headers: list[str]
    rows: list[list[str]]
    highlight_best: bool = True


class TwoColumnContent(BaseModel):
    """双栏对比页。"""

    heading: str
    left_title: str
    left_points: list[str]
    right_title: str
    right_points: list[str]
    left_sentiment: Literal["positive", "neutral"] = "neutral"
    right_sentiment: Literal["negative", "neutral"] = "neutral"


class SummaryContent(BaseModel):
    """总结页。"""

    heading: str
    takeaways: list[str]


class ReferencesContent(BaseModel):
    """参考文献页 — 从 Meta.references 自动生成。"""


SlideContent = (
    TitleContent
    | OutlineContent
    | BulletsContent
    | FormulaContent
    | FigureContent
    | TableContent
    | TwoColumnContent
    | SummaryContent
    | ReferencesContent
)


# ── SlideSchema ──


class SlideSchema(BaseModel):
    """单页幻灯片结构化描述。"""

    id: str
    layout: Literal[
        "title",
        "outline",
        "bullets",
        "formula",
        "figure",
        "table",
        "two_column",
        "summary",
        "references",
    ]
    section: str | None = None
    notes: str | None = None
    citations: list[str] = []
    content: Annotated[SlideContent, Field(discriminator="layout")]


# ── 顶层 ──


class PresentationSchema(BaseModel):
    """完整演示文稿的结构化描述。"""

    meta: PresentationMeta
    slides: list[SlideSchema]
