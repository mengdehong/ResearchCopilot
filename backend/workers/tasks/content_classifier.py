"""内容分类器。将 ParsedDocument 拆分为按 ORM 类型分类的记录字典列表。

纯函数，不依赖数据库或外部服务。
"""

import re
import uuid
from dataclasses import dataclass, field

from backend.services.parser_engine import ParsedDocument

# 超过此 token 数的段落会在句子边界分割
_MAX_CHUNK_TOKENS = 1024

# doc_summary 章节标题关键词 (小写匹配)
_SUMMARY_SECTION_KEYWORDS = frozenset(
    {
        "abstract",
        "conclusion",
        "conclusions",
        "discussion",
        "limitations",
        "summary",
    }
)

# 句子结尾正则: 句号/问号/叹号 后跟空白
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ClassifiedContent:
    """分类结果容器。每个字段是对应 ORM 表的字典列表。"""

    doc_summaries: list[dict[str, object]] = field(default_factory=list)
    paragraphs: list[dict[str, object]] = field(default_factory=list)
    tables: list[dict[str, object]] = field(default_factory=list)
    figures: list[dict[str, object]] = field(default_factory=list)
    equations: list[dict[str, object]] = field(default_factory=list)
    references: list[dict[str, object]] = field(default_factory=list)
    section_headings: list[dict[str, object]] = field(default_factory=list)


def classify_content(
    parsed: ParsedDocument,
    doc_id: uuid.UUID,
) -> ClassifiedContent:
    """将 ParsedDocument 拆分为按 ORM 类型分类的记录列表。"""
    result = ClassifiedContent()

    # --- Abstract 始终作为 doc_summary ---
    if parsed.abstract:
        result.doc_summaries.append(
            {
                "document_id": doc_id,
                "content_type": "abstract",
                "content_text": parsed.abstract,
            }
        )

    # --- 章节处理 ---
    for section in parsed.sections:
        # 提取 section_heading 记录
        result.section_headings.append(
            {
                "document_id": doc_id,
                "heading_text": section.heading,
                "level": section.level,
                "page_number": section.page_numbers[0] if section.page_numbers else 0,
            }
        )

        # 判断是否为摘要类章节
        heading_lower = section.heading.lower()
        section_keyword = _match_summary_keyword(heading_lower)

        if section_keyword:
            result.doc_summaries.append(
                {
                    "document_id": doc_id,
                    "content_type": section_keyword,
                    "content_text": section.content,
                }
            )
        else:
            # 普通章节 → paragraphs (可能需要切分)
            chunks = _split_into_chunks(section.content)
            for idx, chunk_text in enumerate(chunks):
                result.paragraphs.append(
                    {
                        "document_id": doc_id,
                        "section_path": section.heading,
                        "chunk_index": idx,
                        "content_text": chunk_text,
                        "page_numbers": section.page_numbers,
                    }
                )

    # --- 表格 ---
    for table in parsed.tables:
        result.tables.append(
            {
                "document_id": doc_id,
                "section_path": table.section_path,
                "table_title": table.title,
                "page_number": table.page_number,
                "raw_data": table.raw_data,
            }
        )

    # --- 图表 ---
    for figure in parsed.figures:
        result.figures.append(
            {
                "document_id": doc_id,
                "section_path": figure.section_path,
                "caption_text": figure.caption,
                "context_text": figure.context,
                "image_path": figure.image_path,
                "page_number": figure.page_number,
            }
        )

    # --- 公式 ---
    for equation in parsed.equations:
        result.equations.append(
            {
                "document_id": doc_id,
                "section_path": equation.section_path,
                "latex_text": equation.latex,
                "context_text": equation.context,
                "equation_label": equation.label,
                "page_number": equation.page_number,
            }
        )

    # --- 参考文献 ---
    for idx, ref in enumerate(parsed.references):
        result.references.append(
            {
                "document_id": doc_id,
                "ref_index": idx,
                "ref_title": ref.get("title", ""),
                "ref_authors": ref.get("authors"),
                "ref_year": _safe_int(ref.get("year")),
                "ref_doi": ref.get("doi"),
            }
        )

    return result


def _match_summary_keyword(heading_lower: str) -> str | None:
    """匹配摘要类章节关键词, 返回 content_type 或 None。"""
    for keyword in _SUMMARY_SECTION_KEYWORDS:
        if keyword in heading_lower:
            return keyword
    return None


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数 (英文 ≈ word count × 1.3)。"""
    return int(len(text.split()) * 1.3)


def _split_into_chunks(text: str) -> list[str]:
    """将文本按句子边界切分为不超过 _MAX_CHUNK_TOKENS 的 chunks。"""
    if _estimate_tokens(text) <= _MAX_CHUNK_TOKENS:
        return [text]

    sentences = _SENTENCE_BOUNDARY.split(text)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _estimate_tokens(sentence)
        if current_tokens + sentence_tokens > _MAX_CHUNK_TOKENS and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_tokens = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def _safe_int(value: str | None) -> int | None:
    """安全转换字符串为 int, 失败返回 None。"""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
