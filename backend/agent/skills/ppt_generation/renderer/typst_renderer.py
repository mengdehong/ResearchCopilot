"""Typst 渲染后端。将 PresentationSchema 渲染为 .typ 源文件并可选编译为 PDF。"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import TYPE_CHECKING

from backend.agent.skills.ppt_generation.renderer.auto_slides import inject_auto_slides
from backend.agent.skills.ppt_generation.renderer.base import RenderedPresentation
from backend.agent.skills.ppt_generation.schema import (
    BulletsContent,
    FigureContent,
    FormulaContent,
    OutlineContent,
    PresentationMeta,
    PresentationSchema,
    SlideSchema,
    SummaryContent,
    TableContent,
    TwoColumnContent,
)
from backend.core.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


# ── LaTeX → Typst 数学转换 ──

# LaTeX 函数名 → Typst 等效
_LATEX_MATH_FUNCTIONS = [
    "softmax",
    "sigmoid",
    "tanh",
    "relu",
    "Attention",
    "MultiHead",
    "LayerNorm",
    "argmax",
    "argmin",
]


def _latex_to_typst_math(formula: str) -> str:
    """将 LaTeX 数学语法转换为 Typst 兼容语法。

    Typst math mode 中多字母标识符需要用 op() 包裹。
    """
    result = formula

    # \text{...} → "..."
    result = re.sub(r"\\text\{([^}]+)\}", r'"\1"', result)
    # \frac{a}{b} → (a) / (b)
    result = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1) / (\2)", result)
    # \sqrt{x} → sqrt(x)
    result = re.sub(r"\\sqrt\{([^}]+)\}", r"sqrt(\1)", result)
    # \left( → (  \right) → )
    result = result.replace(r"\left(", "(").replace(r"\right)", ")")
    result = result.replace(r"\left[", "[").replace(r"\right]", "]")

    # 多字母函数名 → op("...") 包裹
    for fn in _LATEX_MATH_FUNCTIONS:
        result = re.sub(rf"\b{fn}\b", f'op("{fn}")', result)

    # 相邻单字母变量拆分：mc → m c, QK → Q K
    # Typst 中多字母连写被视为单一标识符，需要空格分隔
    result = re.sub(r'(?<!["\w])([a-zA-Z])([a-zA-Z])(?!["\w(])', r"\1 \2", result)
    # 二次处理覆盖 3+ 连续字母 (abc → a b c)
    result = re.sub(r'(?<!["\w])([a-zA-Z])([a-zA-Z])(?!["\w(])', r"\1 \2", result)

    return result


# ── 版式渲染函数（纯函数） ──


def _render_title(meta: PresentationMeta) -> str:
    """渲染标题页。"""
    lines = [
        "#slide[",
        "  #align(center + horizon)[",
        f'    #text(size: 28pt, weight: "bold")[{meta.title}]',
    ]
    if meta.subtitle:
        lines.append("    #v(0.5em)")
        lines.append(f"    #text(size: 18pt)[{meta.subtitle}]")
    lines.append("    #v(1em)")
    lines.append(f"    #text(size: 14pt)[{', '.join(meta.authors)}]")
    if meta.date:
        lines.append("    #v(0.5em)")
        lines.append(f"    #text(size: 12pt)[{meta.date}]")
    lines.extend(["  ]", "]"])
    return "\n".join(lines)


def _render_outline(content: OutlineContent, sections: list[str]) -> str:
    """渲染目录页。"""
    lines = ["#slide[", '  #text(size: 22pt, weight: "bold")[目录]', "  #v(1em)"]
    for i, section in enumerate(sections):
        marker = "→ " if content.active_index == i else "  "
        weight = '"bold"' if content.active_index == i else '"regular"'
        lines.append(f"  #text(weight: {weight})[{marker}{section}]")
        lines.append("  #v(0.3em)")
    lines.append("]")
    return "\n".join(lines)


def _render_bullets(content: BulletsContent) -> str:
    """渲染要点页。"""
    lines = [
        "#slide[",
        f'  #text(size: 22pt, weight: "bold")[{content.heading}]',
        "  #v(0.5em)",
    ]
    for point in content.points:
        lines.append(f"  - {point}")
    if content.note:
        lines.append("  #v(0.5em)")
        lines.append(f"  #text(size: 10pt, fill: gray)[{content.note}]")
    lines.append("]")
    return "\n".join(lines)


def _render_formula(content: FormulaContent) -> str:
    """渲染公式页。LaTeX 公式自动转换为 Typst 语法。"""
    typst_formula = _latex_to_typst_math(content.formula)
    lines = [
        "#slide[",
        f'  #text(size: 22pt, weight: "bold")[{content.heading}]',
        "  #v(1em)",
        f"  #align(center)[$ {typst_formula} $]",
        "  #v(1em)",
    ]
    for exp in content.explanation:
        lines.append(f"  - {exp}")
    lines.append("]")
    return "\n".join(lines)


def _render_figure(content: FigureContent) -> str:
    """渲染图文页。"""
    lines = [
        "#slide[",
        f'  #text(size: 22pt, weight: "bold")[{content.heading}]',
        "  #v(0.5em)",
        "  #grid(",
        "    columns: (1fr, 1fr),",
        "    gutter: 1em,",
    ]
    img_col = f'    image("{content.image_ref}", width: 100%)'
    text_col_lines = ["    ["]
    for point in content.points:
        text_col_lines.append(f"      - {point}")
    text_col_lines.append("    ]")
    text_col = "\n".join(text_col_lines)

    if content.image_position == "left":
        lines.append(img_col + ",")
        lines.append(text_col + ",")
    else:
        lines.append(text_col + ",")
        lines.append(img_col + ",")
    lines.extend(
        [
            "  )",
            f"  #align(center)[#text(size: 10pt)[{content.caption}]]",
            "]",
        ]
    )
    return "\n".join(lines)


def _render_table(content: TableContent) -> str:
    """渲染表格对比页。"""
    col_count = len(content.headers)
    lines = [
        "#slide[",
        f'  #text(size: 22pt, weight: "bold")[{content.heading}]',
        "  #v(0.5em)",
        "  #table(",
        f"    columns: {col_count},",
        "    align: center,",
    ]
    # Headers
    header_cells = ", ".join(f"[*{h}*]" for h in content.headers)
    lines.append(f"    {header_cells},")
    # Rows
    for row in content.rows:
        row_cells = ", ".join(f"[{cell}]" for cell in row)
        lines.append(f"    {row_cells},")
    lines.extend(["  )", "]"])
    return "\n".join(lines)


def _render_two_column(content: TwoColumnContent) -> str:
    """渲染双栏对比页。"""
    lines = [
        "#slide[",
        f'  #text(size: 22pt, weight: "bold")[{content.heading}]',
        "  #v(0.5em)",
        "  #grid(",
        "    columns: (1fr, 1fr),",
        "    gutter: 1em,",
        "    [",
        f'      #text(weight: "bold")[{content.left_title}]',
    ]
    for point in content.left_points:
        lines.append(f"      - {point}")
    lines.extend(
        [
            "    ],",
            "    [",
            f'      #text(weight: "bold")[{content.right_title}]',
        ]
    )
    for point in content.right_points:
        lines.append(f"      - {point}")
    lines.extend(["    ],", "  )", "]"])
    return "\n".join(lines)


def _render_summary(content: SummaryContent) -> str:
    """渲染总结页。"""
    lines = [
        "#slide[",
        f'  #text(size: 22pt, weight: "bold")[{content.heading}]',
        "  #v(0.5em)",
    ]
    for i, takeaway in enumerate(content.takeaways, 1):
        lines.append(f"  {i}. {takeaway}")
    lines.append("]")
    return "\n".join(lines)


def _render_references(meta: PresentationMeta) -> str:
    """渲染参考文献页。"""
    lines = [
        "#slide[",
        '  #text(size: 22pt, weight: "bold")[参考文献]',
        "  #v(0.5em)",
        "  #set text(size: 10pt)",
    ]
    for ref in meta.references:
        lines.append(f"  [{ref.key}] {ref.text}")
        lines.append("  #v(0.2em)")
    lines.append("]")
    return "\n".join(lines)


# ── TypstRenderer ──


class TypstRenderer:
    """Typst 渲染后端。"""

    def render(
        self,
        schema: PresentationSchema,
        template_dir: Path,
        output_dir: Path,
    ) -> RenderedPresentation:
        """渲染 PresentationSchema 为 Typst 源文件，可选编译为 PDF。"""
        full_schema = inject_auto_slides(schema)

        # 收集 sections 用于目录页渲染
        sections = _collect_sections(schema)

        # 逐页渲染
        slide_fragments: list[str] = []
        for slide in full_schema.slides:
            fragment = _render_slide(slide, full_schema.meta, sections)
            slide_fragments.append(fragment)

        # 组装完整源文件
        source = _assemble_source(full_schema.meta, template_dir, slide_fragments)

        # 写入文件
        output_dir.mkdir(parents=True, exist_ok=True)
        source_path = output_dir / "presentation.typ"
        source_path.write_text(source, encoding="utf-8")

        # 尝试编译
        pdf_path = _compile_typst(source_path)

        return RenderedPresentation(
            source_path=str(source_path),
            pdf_path=str(pdf_path) if pdf_path else None,
            source_type="typst",
            slide_count=len(full_schema.slides),
        )


def _collect_sections(schema: PresentationSchema) -> list[str]:
    """从原始 slides 收集 sections（按出现顺序去重）。"""
    sections: list[str] = []
    for slide in schema.slides:
        if slide.section and slide.section not in sections:
            sections.append(slide.section)
    return sections


def _render_slide(
    slide: SlideSchema,
    meta: PresentationMeta,
    sections: list[str],
) -> str:
    """将单个 SlideSchema 渲染为 Typst 代码片段。"""
    content = slide.content
    match slide.layout:
        case "title":
            return _render_title(meta)
        case "outline":
            assert isinstance(content, OutlineContent)
            return _render_outline(content, sections)
        case "bullets":
            assert isinstance(content, BulletsContent)
            return _render_bullets(content)
        case "formula":
            assert isinstance(content, FormulaContent)
            return _render_formula(content)
        case "figure":
            assert isinstance(content, FigureContent)
            return _render_figure(content)
        case "table":
            assert isinstance(content, TableContent)
            return _render_table(content)
        case "two_column":
            assert isinstance(content, TwoColumnContent)
            return _render_two_column(content)
        case "summary":
            assert isinstance(content, SummaryContent)
            return _render_summary(content)
        case "references":
            return _render_references(meta)
        case _:
            raise ValueError(f"Unknown layout: {slide.layout}")


def _assemble_source(
    meta: PresentationMeta,
    template_dir: Path,
    fragments: list[str],
) -> str:
    """组装完整 Typst 源文件。主题内联嵌入，确保文件自包含。"""
    preamble_lines = [
        "// Auto-generated by PPT Generation Skill",
        f"// Title: {meta.title}",
        "",
        "// ── 页面和字体设置 ──",
        '#set page(width: 254mm, height: 142.9mm, margin: 1.5cm, fill: rgb("#f8fafc"))',
        '#set text(size: 14pt, fill: rgb("#1e293b"))',
        "",
        "// ── slide 函数：每个 slide 占一页 ──",
        "#let slide(body) = {",
        "  pagebreak(weak: true)",
        "  body",
        "}",
        "",
    ]

    body = "\n\n".join(fragments)
    return "\n".join(preamble_lines) + "\n" + body + "\n"


def _compile_typst(source_path: Path) -> Path | None:
    """尝试用 typst CLI 编译 .typ 为 PDF。返回 PDF 路径或 None。"""
    if not shutil.which("typst"):
        logger.warning("typst_not_found", msg="typst CLI not available, skipping PDF compilation")
        return None

    pdf_path = source_path.with_suffix(".pdf")
    try:
        subprocess.run(
            ["typst", "compile", str(source_path), str(pdf_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        logger.info("typst_compile_done", pdf_path=str(pdf_path))
        return pdf_path
    except subprocess.CalledProcessError as exc:
        logger.error(
            "typst_compile_failed",
            stderr=exc.stderr,
            returncode=exc.returncode,
        )
        raise
