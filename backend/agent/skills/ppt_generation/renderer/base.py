"""渲染后端统一协议和结果数据类。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from pathlib import Path

    from backend.agent.skills.ppt_generation.schema import PresentationSchema


class RenderedPresentation(BaseModel):
    """渲染结果。"""

    source_path: str
    pdf_path: str | None
    source_type: Literal["typst", "latex"]
    slide_count: int


class SlideRenderer(Protocol):
    """渲染后端统一协议。"""

    def render(
        self,
        schema: PresentationSchema,
        template_dir: Path,
        output_dir: Path,
    ) -> RenderedPresentation: ...
