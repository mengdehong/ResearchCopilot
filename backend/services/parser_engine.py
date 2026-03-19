"""PDF 解析引擎。封装 MinerU 和 PyMuPDF fallback。"""
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from backend.core.logger import get_logger

logger = get_logger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]


class ParseQuality(StrEnum):
    FULL = "full"
    DEGRADED = "degraded"


@dataclass
class ParsedSection:
    """解析出的章节。"""
    heading: str
    level: int
    content: str
    page_numbers: list[int] = field(default_factory=list)


@dataclass
class ParsedTable:
    """解析出的表格。"""
    title: str
    raw_data: dict[str, object]
    page_number: int
    section_path: str = ""


@dataclass
class ParsedFigure:
    """解析出的图表。"""
    caption: str
    image_path: str
    context: str
    page_number: int
    section_path: str = ""


@dataclass
class ParsedEquation:
    """解析出的公式。"""
    latex: str
    context: str
    label: str | None = None
    page_number: int = 0
    section_path: str = ""


@dataclass
class ParsedDocument:
    """完整的解析结果。"""
    title: str
    abstract: str
    sections: list[ParsedSection] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    figures: list[ParsedFigure] = field(default_factory=list)
    equations: list[ParsedEquation] = field(default_factory=list)
    references: list[dict[str, str]] = field(default_factory=list)
    quality: ParseQuality = ParseQuality.FULL


class PdfParser(Protocol):
    """PDF 解析器抽象接口。"""
    def parse(self, pdf_path: Path) -> ParsedDocument: ...


class MinerUParser:
    """MinerU GPU 解析器。"""

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """调用 MinerU 解析 PDF 为结构化文档。"""
        logger.info("mineru_parse_start", path=str(pdf_path))
        try:
            # MinerU API 调用(实际集成时填充)
            # from magic_pdf.pipe.UNIPipe import UNIPipe
            raise NotImplementedError("MinerU integration pending")
        except Exception:
            logger.warning("mineru_parse_failed_fallback", path=str(pdf_path))
            return FallbackParser().parse(pdf_path)


class FallbackParser:
    """PyMuPDF 纯文本 fallback 解析器。"""

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """降级解析: 仅提取纯文本。"""
        if fitz is None:
            raise ImportError("PyMuPDF (fitz) is not installed")

        logger.info("fallback_parse_start", path=str(pdf_path))
        doc = fitz.open(str(pdf_path))
        text_parts: list[str] = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()

        full_text = "\n".join(text_parts)
        return ParsedDocument(
            title=pdf_path.stem,
            abstract="",
            sections=[
                ParsedSection(heading="Full Text", level=1, content=full_text),
            ],
            quality=ParseQuality.DEGRADED,
        )
