"""内容分类器单元测试。将 ParsedDocument 拆分为按 ORM 类型分类的记录列表。"""
import uuid

import pytest

from backend.services.parser_engine import (
    ParsedDocument,
    ParsedEquation,
    ParsedFigure,
    ParsedSection,
    ParsedTable,
)

DOC_ID = uuid.uuid4()


def _make_parsed_doc(
    *,
    sections: list[ParsedSection] | None = None,
    tables: list[ParsedTable] | None = None,
    figures: list[ParsedFigure] | None = None,
    equations: list[ParsedEquation] | None = None,
    references: list[dict[str, str]] | None = None,
    abstract: str = "Test abstract.",
) -> ParsedDocument:
    return ParsedDocument(
        title="Test Paper",
        abstract=abstract,
        sections=sections or [],
        tables=tables or [],
        figures=figures or [],
        equations=equations or [],
        references=references or [],
    )


# --- 导入测试目标 ---

def test_classify_returns_classified_content() -> None:
    """classify_content 应返回 ClassifiedContent dataclass。"""
    from backend.workers.tasks.content_classifier import (
        ClassifiedContent,
        classify_content,
    )

    parsed = _make_parsed_doc()
    result = classify_content(parsed, DOC_ID)

    assert isinstance(result, ClassifiedContent)


def test_abstract_classified_as_doc_summary() -> None:
    """abstract 应被分类为 doc_summary, content_type='abstract'。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(abstract="This paper presents...")
    result = classify_content(parsed, DOC_ID)

    abstracts = [s for s in result.doc_summaries if s["content_type"] == "abstract"]
    assert len(abstracts) == 1
    assert abstracts[0]["content_text"] == "This paper presents..."
    assert abstracts[0]["document_id"] == DOC_ID


def test_conclusion_section_classified_as_doc_summary() -> None:
    """标题含 'conclusion' 的章节应归入 doc_summary。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(sections=[
        ParsedSection(heading="5. Conclusion", level=1, content="We showed that...", page_numbers=[10]),
    ])
    result = classify_content(parsed, DOC_ID)

    conclusions = [s for s in result.doc_summaries if s["content_type"] == "conclusion"]
    assert len(conclusions) == 1
    assert "We showed that" in conclusions[0]["content_text"]


def test_discussion_section_classified_as_doc_summary() -> None:
    """标题含 'discussion' 的章节应归入 doc_summary。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(sections=[
        ParsedSection(heading="Discussion", level=1, content="Our results...", page_numbers=[8]),
    ])
    result = classify_content(parsed, DOC_ID)

    discussions = [s for s in result.doc_summaries if s["content_type"] == "discussion"]
    assert len(discussions) == 1


def test_regular_section_classified_as_paragraph() -> None:
    """普通章节应被切分为 paragraphs。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(sections=[
        ParsedSection(heading="3. Methods", level=1, content="We used method A.", page_numbers=[5]),
    ])
    result = classify_content(parsed, DOC_ID)

    assert len(result.paragraphs) >= 1
    assert result.paragraphs[0]["content_text"] == "We used method A."
    assert result.paragraphs[0]["section_path"] == "3. Methods"
    assert result.paragraphs[0]["document_id"] == DOC_ID


def test_long_paragraph_split_at_sentence_boundary() -> None:
    """超 1024 tokens 的段落应在句子边界分割。"""
    from backend.workers.tasks.content_classifier import classify_content

    # 创建一段超长文本 (每个句子约 10 words ≈ 13 tokens)
    sentences = [f"This is sentence number {i} with some extra words." for i in range(200)]
    long_content = " ".join(sentences)

    parsed = _make_parsed_doc(sections=[
        ParsedSection(heading="Long Section", level=1, content=long_content, page_numbers=[1, 2]),
    ])
    result = classify_content(parsed, DOC_ID)

    # 应被分成多个 chunk
    assert len(result.paragraphs) > 1
    # 每个 chunk 应以句尾结束 (以 . 结尾)
    for p in result.paragraphs:
        assert p["content_text"].rstrip().endswith(".")
    # chunk_index 应连续
    indices = [p["chunk_index"] for p in result.paragraphs]
    assert indices == list(range(len(indices)))


def test_tables_classified() -> None:
    """tables 应被正确映射为表格记录。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(tables=[
        ParsedTable(title="Table 1", raw_data={"rows": [["a"]]}, page_number=3, section_path="Results"),
    ])
    result = classify_content(parsed, DOC_ID)

    assert len(result.tables) == 1
    assert result.tables[0]["table_title"] == "Table 1"
    assert result.tables[0]["raw_data"] == {"rows": [["a"]]}
    assert result.tables[0]["document_id"] == DOC_ID


def test_figures_classified() -> None:
    """figures 应被正确映射为图表记录。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(figures=[
        ParsedFigure(caption="Figure 1", image_path="/img/1.png", context="Shows X", page_number=4, section_path="Results"),
    ])
    result = classify_content(parsed, DOC_ID)

    assert len(result.figures) == 1
    assert result.figures[0]["caption_text"] == "Figure 1"
    assert result.figures[0]["image_path"] == "/img/1.png"


def test_equations_classified() -> None:
    """equations 应被正确映射为公式记录。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(equations=[
        ParsedEquation(latex="E=mc^2", context="energy", label="eq1", page_number=2, section_path="Theory"),
    ])
    result = classify_content(parsed, DOC_ID)

    assert len(result.equations) == 1
    assert result.equations[0]["latex_text"] == "E=mc^2"
    assert result.equations[0]["equation_label"] == "eq1"


def test_references_classified() -> None:
    """references 应被映射为引用记录列表。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(references=[
        {"title": "Paper A", "authors": "Smith et al.", "year": "2024", "doi": "10.1234/a"},
    ])
    result = classify_content(parsed, DOC_ID)

    assert len(result.references) == 1
    assert result.references[0]["ref_title"] == "Paper A"
    assert result.references[0]["ref_index"] == 0


def test_section_headings_classified() -> None:
    """section 标题应被提取为 section_headings 记录。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(sections=[
        ParsedSection(heading="1. Introduction", level=1, content="Intro text.", page_numbers=[1]),
        ParsedSection(heading="1.1 Background", level=2, content="Background text.", page_numbers=[1]),
    ])
    result = classify_content(parsed, DOC_ID)

    assert len(result.section_headings) == 2
    assert result.section_headings[0]["heading_text"] == "1. Introduction"
    assert result.section_headings[0]["level"] == 1
    assert result.section_headings[1]["heading_text"] == "1.1 Background"
    assert result.section_headings[1]["level"] == 2


def test_empty_document() -> None:
    """空文档只有 abstract 的 doc_summary, 其他列表为空。"""
    from backend.workers.tasks.content_classifier import classify_content

    parsed = _make_parsed_doc(abstract="Just abstract.")
    result = classify_content(parsed, DOC_ID)

    assert len(result.doc_summaries) == 1  # abstract only
    assert len(result.paragraphs) == 0
    assert len(result.tables) == 0
    assert len(result.figures) == 0
    assert len(result.equations) == 0
    assert len(result.references) == 0
    assert len(result.section_headings) == 0
