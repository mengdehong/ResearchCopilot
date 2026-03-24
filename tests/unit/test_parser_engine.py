"""Parser Engine 单元测试(mock PyMuPDF/fitz)。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.services.parser_engine import (
    FallbackParser,
    MinerUParser,
    ParsedDocument,
    ParseQuality,
)


@patch("backend.services.parser_engine.fitz")
def test_fallback_parser_extracts_text(mock_fitz: MagicMock) -> None:
    """FallbackParser 通过 PyMuPDF 提取纯文本并标记为 DEGRADED。"""
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Hello world"
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_fitz.open.return_value = mock_doc

    parser = FallbackParser()
    result = parser.parse(Path("/tmp/test.pdf"))

    assert isinstance(result, ParsedDocument)
    assert result.quality == ParseQuality.DEGRADED
    assert result.title == "test"
    assert len(result.sections) == 1
    assert "Hello world" in result.sections[0].content
    mock_doc.close.assert_called_once()


@patch("backend.services.parser_engine.fitz")
def test_mineru_parser_falls_back(mock_fitz: MagicMock) -> None:
    """MinerU 未集成时应降级到 FallbackParser。"""
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Fallback content"
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_fitz.open.return_value = mock_doc

    parser = MinerUParser()
    result = parser.parse(Path("/tmp/paper.pdf"))

    assert result.quality == ParseQuality.DEGRADED
    assert result.title == "paper"
