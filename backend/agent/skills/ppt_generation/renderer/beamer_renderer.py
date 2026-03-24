"""Beamer (LaTeX) 渲染后端。将 PresentationSchema 渲染为 .tex 文件并可选编译为 PDF。"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

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


# ── 版式渲染函数（纯函数） ──


def _escape_latex(text: str) -> str:
    """转义 LaTeX 特殊字符。"""
    specials = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}
    for char, escaped in specials.items():
        text = text.replace(char, escaped)
    return text


def _render_title(meta: PresentationMeta) -> str:
    """渲染标题页。"""
    return "\\begin{frame}\n  \\titlepage\n\\end{frame}\n"


def _render_outline(content: OutlineContent) -> str:
    """渲染目录页。"""
    return "\\begin{frame}{目录}\n  \\tableofcontents\n\\end{frame}\n"


def _render_bullets(content: BulletsContent) -> str:
    """渲染要点页。"""
    lines = [f"\\begin{{frame}}{{{_escape_latex(content.heading)}}}", "  \\begin{itemize}"]
    for point in content.points:
        lines.append(f"    \\item {_escape_latex(point)}")
    lines.append("  \\end{itemize}")
    if content.note:
        lines.append("  \\vspace{0.5em}")
        lines.append(f"  \\footnotesize{{{_escape_latex(content.note)}}}")
    lines.append("\\end{frame}")
    return "\n".join(lines)


def _render_formula(content: FormulaContent) -> str:
    """渲染公式页。"""
    lines = [
        f"\\begin{{frame}}{{{_escape_latex(content.heading)}}}",
        f"  \\[ {content.formula} \\]",
        "  \\begin{itemize}",
    ]
    for exp in content.explanation:
        lines.append(f"    \\item {_escape_latex(exp)}")
    lines.extend(["  \\end{itemize}", "\\end{frame}"])
    return "\n".join(lines)


def _render_figure(content: FigureContent) -> str:
    """渲染图文页。"""
    lines = [
        f"\\begin{{frame}}{{{_escape_latex(content.heading)}}}",
        "  \\begin{columns}",
        "    \\begin{column}{0.5\\textwidth}",
        f"      \\includegraphics[width=\\textwidth]{{{content.image_ref}}}",
        f"      \\caption{{{_escape_latex(content.caption)}}}",
        "    \\end{column}",
        "    \\begin{column}{0.5\\textwidth}",
        "      \\begin{itemize}",
    ]
    for point in content.points:
        lines.append(f"        \\item {_escape_latex(point)}")
    lines.extend(
        [
            "      \\end{itemize}",
            "    \\end{column}",
            "  \\end{columns}",
            "\\end{frame}",
        ]
    )
    return "\n".join(lines)


def _render_table(content: TableContent) -> str:
    """渲染表格对比页。"""
    col_spec = "|".join(["c"] * len(content.headers))
    lines = [
        f"\\begin{{frame}}{{{_escape_latex(content.heading)}}}",
        f"  \\begin{{tabular}}{{|{col_spec}|}}",
        "    \\hline",
        "    " + " & ".join(f"\\textbf{{{_escape_latex(h)}}}" for h in content.headers) + " \\\\",
        "    \\hline",
    ]
    for row in content.rows:
        lines.append("    " + " & ".join(_escape_latex(cell) for cell in row) + " \\\\")
        lines.append("    \\hline")
    lines.extend(["  \\end{tabular}", "\\end{frame}"])
    return "\n".join(lines)


def _render_two_column(content: TwoColumnContent) -> str:
    """渲染双栏对比页。"""
    lines = [
        f"\\begin{{frame}}{{{_escape_latex(content.heading)}}}",
        "  \\begin{columns}",
        "    \\begin{column}{0.5\\textwidth}",
        f"      \\textbf{{{_escape_latex(content.left_title)}}}",
        "      \\begin{itemize}",
    ]
    for point in content.left_points:
        lines.append(f"        \\item {_escape_latex(point)}")
    lines.extend(
        [
            "      \\end{itemize}",
            "    \\end{column}",
            "    \\begin{column}{0.5\\textwidth}",
            f"      \\textbf{{{_escape_latex(content.right_title)}}}",
            "      \\begin{itemize}",
        ]
    )
    for point in content.right_points:
        lines.append(f"        \\item {_escape_latex(point)}")
    lines.extend(
        [
            "      \\end{itemize}",
            "    \\end{column}",
            "  \\end{columns}",
            "\\end{frame}",
        ]
    )
    return "\n".join(lines)


def _render_summary(content: SummaryContent) -> str:
    """渲染总结页。"""
    lines = [
        f"\\begin{{frame}}{{{_escape_latex(content.heading)}}}",
        "  \\begin{enumerate}",
    ]
    for takeaway in content.takeaways:
        lines.append(f"    \\item {_escape_latex(takeaway)}")
    lines.extend(["  \\end{enumerate}", "\\end{frame}"])
    return "\n".join(lines)


def _render_references(meta: PresentationMeta) -> str:
    """渲染参考文献页。"""
    lines = [
        "\\begin{frame}{参考文献}",
        "  \\footnotesize",
        "  \\begin{itemize}",
    ]
    for ref in meta.references:
        lines.append(f"    \\item[{_escape_latex(ref.key)}] {_escape_latex(ref.text)}")
    lines.extend(["  \\end{itemize}", "\\end{frame}"])
    return "\n".join(lines)


# ── BeamerRenderer ──


def _render_slide(
    slide: SlideSchema,
    meta: PresentationMeta,
) -> str:
    """将单个 SlideSchema 渲染为 Beamer LaTeX 代码片段。"""
    content = slide.content
    match slide.layout:
        case "title":
            return _render_title(meta)
        case "outline":
            assert isinstance(content, OutlineContent)
            return _render_outline(content)
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


def _assemble_source(meta: PresentationMeta, fragments: list[str]) -> str:
    """组装完整 Beamer LaTeX 源文件。"""
    preamble = [
        "% Auto-generated by PPT Generation Skill (Beamer backend)",
        "\\documentclass[aspectratio=169]{beamer}",
        "\\usetheme{metropolis}",
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage{graphicx}",
        "\\usepackage{amsmath}",
        "",
        f"\\title{{{_escape_latex(meta.title)}}}",
    ]
    if meta.subtitle:
        preamble.append(f"\\subtitle{{{_escape_latex(meta.subtitle)}}}")
    preamble.append(f"\\author{{{', '.join(_escape_latex(a) for a in meta.authors)}}}")
    if meta.date:
        preamble.append(f"\\date{{{_escape_latex(meta.date)}}}")
    else:
        preamble.append("\\date{\\today}")
    preamble.extend(["", "\\begin{document}", ""])

    body = "\n\n".join(fragments)
    epilogue = "\n\\end{document}\n"

    return "\n".join(preamble) + "\n" + body + epilogue


def _compile_pdflatex(source_path: Path) -> Path | None:
    """尝试用 pdflatex 编译 .tex 为 PDF。返回 PDF 路径或 None。"""
    if not shutil.which("pdflatex"):
        logger.warning("pdflatex_not_found", msg="pdflatex not available, skipping PDF compilation")
        return None

    pdf_path = source_path.with_suffix(".pdf")
    try:
        # 运行两次以解析交叉引用
        for _ in range(2):
            subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-output-directory",
                    str(source_path.parent),
                    str(source_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        logger.info("pdflatex_compile_done", pdf_path=str(pdf_path))
        return pdf_path
    except subprocess.CalledProcessError as exc:
        logger.error(
            "pdflatex_compile_failed",
            stderr=exc.stderr[:500],
            returncode=exc.returncode,
        )
        raise


class BeamerRenderer:
    """Beamer (LaTeX) 渲染后端。"""

    def render(
        self,
        schema: PresentationSchema,
        template_dir: Path,
        output_dir: Path,
    ) -> RenderedPresentation:
        """渲染 PresentationSchema 为 Beamer .tex 文件，可选编译为 PDF。"""
        # 逐页渲染
        slide_fragments: list[str] = []
        for slide in schema.slides:
            fragment = _render_slide(slide, schema.meta)
            slide_fragments.append(fragment)

        # 组装完整源文件
        source = _assemble_source(schema.meta, slide_fragments)

        # 写入文件
        output_dir.mkdir(parents=True, exist_ok=True)
        source_path = output_dir / "presentation.tex"
        source_path.write_text(source, encoding="utf-8")

        # 尝试编译
        pdf_path = _compile_pdflatex(source_path)

        return RenderedPresentation(
            source_path=str(source_path),
            pdf_path=str(pdf_path) if pdf_path else None,
            source_type="latex",
            slide_count=len(schema.slides),
        )
