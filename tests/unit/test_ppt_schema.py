"""PPT Slide Schema 数据模型测试。"""

from backend.agent.skills.ppt_generation.schema import (
    BulletsContent,
    FigureContent,
    FormulaContent,
    OutlineContent,
    PresentationMeta,
    PresentationSchema,
    Reference,
    ReferencesContent,
    SlideSchema,
    SummaryContent,
    TableContent,
    TitleContent,
    TwoColumnContent,
)


# ── PresentationMeta ──


def test_meta_minimal() -> None:
    meta = PresentationMeta(
        scene="paper_presentation",
        title="Attention Is All You Need",
        authors=["Vaswani et al."],
    )
    assert meta.language == "zh"
    assert meta.references == []


def test_meta_with_references() -> None:
    ref = Reference(key="vaswani2017", text="Vaswani et al., 2017")
    meta = PresentationMeta(
        scene="paper_presentation",
        title="Test",
        authors=["A"],
        references=[ref],
    )
    assert len(meta.references) == 1
    assert meta.references[0].key == "vaswani2017"


# ── SlideSchema ──


def test_slide_schema_bullets() -> None:
    content = BulletsContent(heading="Key Points", points=["Point 1", "Point 2"])
    slide = SlideSchema(id="s1", layout="bullets", content=content)
    assert slide.layout == "bullets"
    assert slide.section is None
    assert slide.citations == []


def test_slide_schema_with_section_and_citations() -> None:
    content = BulletsContent(heading="Background", points=["Context"])
    slide = SlideSchema(
        id="s2",
        layout="bullets",
        section="研究背景",
        citations=["vaswani2017"],
        content=content,
    )
    assert slide.section == "研究背景"
    assert "vaswani2017" in slide.citations


# ── 9 种版式 Content ──


def test_title_content() -> None:
    content = TitleContent()
    assert content is not None


def test_outline_content_default() -> None:
    content = OutlineContent()
    assert content.active_index is None


def test_outline_content_with_index() -> None:
    content = OutlineContent(active_index=2)
    assert content.active_index == 2


def test_bullets_content() -> None:
    content = BulletsContent(heading="H", points=["a", "$x^2$"])
    assert len(content.points) == 2
    assert content.note is None


def test_formula_content() -> None:
    content = FormulaContent(
        heading="Attention",
        formula=r"\text{Attention}(Q,K,V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V",
        explanation=["Q: query matrix", "K: key matrix"],
    )
    assert "Attention" in content.formula
    assert len(content.explanation) == 2


def test_figure_content_default_layout() -> None:
    content = FigureContent(
        heading="Architecture",
        image_ref="images/arch.png",
        caption="Model architecture",
        points=["Encoder-decoder"],
    )
    assert content.layout == "left_img"


def test_table_content() -> None:
    content = TableContent(
        heading="Results",
        headers=["Model", "BLEU"],
        rows=[["Transformer", "28.4"], ["LSTM", "25.1"]],
    )
    assert len(content.rows) == 2
    assert content.highlight_best is True


def test_two_column_content() -> None:
    content = TwoColumnContent(
        heading="Comparison",
        left_title="Pros",
        left_points=["Fast"],
        right_title="Cons",
        right_points=["Complex"],
    )
    assert content.left_sentiment == "neutral"
    assert content.right_sentiment == "neutral"


def test_two_column_content_with_sentiment() -> None:
    content = TwoColumnContent(
        heading="C",
        left_title="L",
        left_points=["a"],
        right_title="R",
        right_points=["b"],
        left_sentiment="positive",
        right_sentiment="negative",
    )
    assert content.left_sentiment == "positive"


def test_summary_content() -> None:
    content = SummaryContent(heading="Summary", takeaways=["Key finding 1"])
    assert len(content.takeaways) == 1


def test_references_content() -> None:
    content = ReferencesContent()
    assert content is not None


# ── PresentationSchema ──


def test_presentation_schema_full() -> None:
    meta = PresentationMeta(
        scene="paper_presentation",
        title="Test Presentation",
        authors=["Author A"],
        references=[Reference(key="ref1", text="Ref 1")],
    )
    slides = [
        SlideSchema(
            id="s1",
            layout="bullets",
            section="Introduction",
            content=BulletsContent(heading="Intro", points=["Point"]),
        ),
        SlideSchema(
            id="s2",
            layout="formula",
            section="Method",
            content=FormulaContent(
                heading="F",
                formula="E=mc^2",
                explanation=["E: energy"],
            ),
        ),
    ]
    schema = PresentationSchema(meta=meta, slides=slides)
    assert len(schema.slides) == 2
    assert schema.meta.title == "Test Presentation"


def test_presentation_schema_serialization() -> None:
    meta = PresentationMeta(
        scene="literature_review",
        title="Survey",
        authors=["B"],
    )
    schema = PresentationSchema(meta=meta, slides=[])
    data = schema.model_dump()
    assert data["meta"]["scene"] == "literature_review"
    assert data["slides"] == []
    # Roundtrip
    restored = PresentationSchema.model_validate(data)
    assert restored.meta.title == "Survey"
