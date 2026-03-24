"""PPT 渲染引擎测试。覆盖 auto_slides 注入、TypstRenderer 源文件生成、工厂函数。"""

import pytest

from backend.agent.skills.ppt_generation.renderer.auto_slides import inject_auto_slides
from backend.agent.skills.ppt_generation.renderer.base import RenderedPresentation
from backend.agent.skills.ppt_generation.renderer.factory import create_renderer
from backend.agent.skills.ppt_generation.renderer.typst_renderer import TypstRenderer
from backend.agent.skills.ppt_generation.schema import (
    BulletsContent,
    FormulaContent,
    PresentationMeta,
    PresentationSchema,
    Reference,
    SlideSchema,
    SummaryContent,
    TableContent,
    TwoColumnContent,
)


def _make_schema(
    slides: list[SlideSchema] | None = None,
    references: list[Reference] | None = None,
) -> PresentationSchema:
    """构造测试用 PresentationSchema。"""
    return PresentationSchema(
        meta=PresentationMeta(
            scene="paper_presentation",
            title="Test Presentation",
            subtitle="A Subtitle",
            authors=["Author A", "Author B"],
            references=references or [],
        ),
        slides=slides
        or [
            SlideSchema(
                id="s1",
                layout="bullets",
                section="Introduction",
                content=BulletsContent(heading="Background", points=["Point 1"]),
            ),
            SlideSchema(
                id="s2",
                layout="bullets",
                section="Method",
                content=BulletsContent(heading="Approach", points=["Step 1"]),
                citations=["ref1"],
            ),
        ],
    )


# ── inject_auto_slides ──


def test_inject_auto_slides_adds_title_page() -> None:
    schema = _make_schema()
    result = inject_auto_slides(schema)
    assert result.slides[0].layout == "title"


def test_inject_auto_slides_adds_outline_pages() -> None:
    schema = _make_schema()
    result = inject_auto_slides(schema)
    outline_slides = [s for s in result.slides if s.layout == "outline"]
    # 两个不同 section，每个 section 前插入一个目录页
    assert len(outline_slides) == 2


def test_inject_auto_slides_adds_references_page() -> None:
    refs = [Reference(key="ref1", text="Paper 1")]
    schema = _make_schema(references=refs)
    result = inject_auto_slides(schema)
    assert result.slides[-1].layout == "references"


def test_inject_auto_slides_no_references_if_empty() -> None:
    schema = _make_schema(references=[])
    # 移除所有 slide 的 citations
    for slide in schema.slides:
        slide.citations = []
    result = inject_auto_slides(schema)
    assert result.slides[-1].layout != "references"


def test_inject_auto_slides_preserves_original() -> None:
    """inject_auto_slides 是纯函数，不修改输入。"""
    schema = _make_schema()
    original_len = len(schema.slides)
    inject_auto_slides(schema)
    assert len(schema.slides) == original_len


# ── RenderedPresentation ──


def test_rendered_presentation_fields() -> None:
    rp = RenderedPresentation(
        source_path="/tmp/test.typ",
        pdf_path="/tmp/test.pdf",
        source_type="typst",
        slide_count=10,
    )
    assert rp.source_type == "typst"
    assert rp.slide_count == 10


def test_rendered_presentation_pdf_none() -> None:
    rp = RenderedPresentation(
        source_path="/tmp/test.typ",
        pdf_path=None,
        source_type="typst",
        slide_count=5,
    )
    assert rp.pdf_path is None


# ── TypstRenderer ──


def test_typst_renderer_generates_source(tmp_path: object) -> None:
    from pathlib import Path

    output_dir = Path(str(tmp_path))
    template_dir = Path(__file__).resolve().parents[2] / (
        "backend/agent/skills/ppt_generation/templates/typst/academic_blue"
    )
    renderer = TypstRenderer()
    schema = _make_schema(
        references=[Reference(key="ref1", text="Paper 1")],
    )

    result = renderer.render(schema, template_dir=template_dir, output_dir=output_dir)

    assert result.source_path is not None
    source_file = Path(result.source_path)
    assert source_file.exists()
    assert source_file.suffix == ".typ"
    assert result.slide_count > 0


def test_typst_renderer_source_contains_content(tmp_path: object) -> None:
    from pathlib import Path

    output_dir = Path(str(tmp_path))
    template_dir = Path(__file__).resolve().parents[2] / (
        "backend/agent/skills/ppt_generation/templates/typst/academic_blue"
    )
    renderer = TypstRenderer()
    slides = [
        SlideSchema(
            id="s1",
            layout="bullets",
            section="Intro",
            content=BulletsContent(heading="Key Points", points=["Alpha", "Beta"]),
        ),
        SlideSchema(
            id="s2",
            layout="formula",
            section="Method",
            content=FormulaContent(
                heading="Equation",
                formula="E=mc^2",
                explanation=["E: energy"],
            ),
        ),
        SlideSchema(
            id="s3",
            layout="table",
            section="Results",
            content=TableContent(
                heading="Comparison",
                headers=["Model", "Score"],
                rows=[["A", "90"], ["B", "85"]],
            ),
        ),
        SlideSchema(
            id="s4",
            layout="two_column",
            section="Discussion",
            content=TwoColumnContent(
                heading="Pros vs Cons",
                left_title="Pros",
                left_points=["Fast"],
                right_title="Cons",
                right_points=["Complex"],
            ),
        ),
        SlideSchema(
            id="s5",
            layout="summary",
            section="Conclusion",
            content=SummaryContent(heading="Summary", takeaways=["Finding 1"]),
        ),
    ]
    schema = _make_schema(slides=slides)

    result = renderer.render(schema, template_dir=template_dir, output_dir=output_dir)
    source_content = Path(result.source_path).read_text()

    assert "Key Points" in source_content
    assert "E=m c^2" in source_content  # LaTeX mc → Typst m c
    assert "Comparison" in source_content
    assert "Pros vs Cons" in source_content
    assert "Summary" in source_content


# ── Factory ──


def test_factory_creates_typst_renderer() -> None:
    renderer = create_renderer("typst")
    assert isinstance(renderer, TypstRenderer)


def test_factory_creates_beamer_renderer() -> None:
    """pdflatex があれば BeamerRenderer を返し、なければ EnvironmentError を即座に上げる。"""
    import shutil

    from backend.agent.skills.ppt_generation.renderer.beamer_renderer import BeamerRenderer

    if shutil.which("pdflatex"):
        renderer = create_renderer("beamer")
        assert isinstance(renderer, BeamerRenderer)
    else:
        with pytest.raises(EnvironmentError, match="pdflatex is required"):
            create_renderer("beamer")


def test_beamer_renderer_raises_early_without_pdflatex(monkeypatch: pytest.MonkeyPatch) -> None:
    """BeamerRenderer.__init__ は pdflatex が存在しなければ即座に EnvironmentError を上げる。"""
    import shutil

    from backend.agent.skills.ppt_generation.renderer.beamer_renderer import BeamerRenderer

    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    with pytest.raises(EnvironmentError, match="pdflatex is required"):
        BeamerRenderer()


def test_factory_rejects_unsupported_backend() -> None:
    with pytest.raises(NotImplementedError, match="html"):
        create_renderer("html")
