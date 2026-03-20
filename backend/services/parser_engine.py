"""PDF 解析引擎。封装 MinerU 和 PyMuPDF fallback。"""
import time
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
    """MinerU GPU 解析器 (API 接入)。"""

    def __init__(self, *, api_url: str | None = None, api_key: str | None = None) -> None:
        from backend.core.config import Settings
        settings = Settings()
        self._api_url = api_url or settings.mineru_api_url
        self._api_key = api_key or settings.mineru_api_key

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """调用 MinerU HTTP API 解析 PDF 为结构化文档。"""
        start = time.monotonic()
        logger.info("mineru_parse_start", path=str(pdf_path))

        if not self._api_key:
            logger.warning("mineru_no_api_key_fallback", path=str(pdf_path))
            return FallbackParser().parse(pdf_path)

        import io
        import zipfile

        import httpx

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

        try:
            with httpx.Client() as client:
                # 1. 获取上传链接
                url = f"{self._api_url}/file-urls/batch"
                payload = {
                    "files": [{"name": pdf_path.name}],
                    "model_version": "vlm",
                }
                res = client.post(url, headers=headers, json=payload, timeout=30)
                res.raise_for_status()
                data = res.json()

                if data.get("code") != 0:
                    raise RuntimeError(f"Request upload URL failed: {data}")

                result = data.get("data", {})
                batch_id = str(result.get("batch_id"))
                file_urls = result.get("file_urls") or result.get("files") or []
                if not batch_id or not file_urls:
                    raise RuntimeError("No upload URL returned")
                upload_url = str(file_urls[0])

                # 2. 上传文件
                with pdf_path.open("rb") as f:
                    # PUT upload does not need auth headers
                    put_res = client.put(upload_url, content=f.read(), timeout=120)
                    put_res.raise_for_status()

                # 3. 轮询结果
                poll_url = f"{self._api_url}/extract-results/batch/{batch_id}"
                start_time = time.time()
                zip_url = ""

                while True:
                    if time.time() - start_time > 300:
                        raise TimeoutError("MinerU task polling timed out")

                    poll_res = client.get(poll_url, headers=headers, timeout=30)
                    poll_res.raise_for_status()
                    poll_data = poll_res.json()

                    if poll_data.get("code") != 0:
                        raise RuntimeError(f"Poll failed: {poll_data}")

                    extract_result = poll_data.get("data", {}).get("extract_result", [])
                    if isinstance(extract_result, dict):
                        extract_items = [extract_result]
                    else:
                        extract_items = extract_result

                    if extract_items:
                        item = extract_items[0]
                        state = item.get("state", "")
                        if state == "done":
                            zip_url = item.get("full_zip_url", "")
                            break
                        if state == "failed":
                            raise RuntimeError(f"MinerU task failed: {item.get('err_msg', '')}")

                    time.sleep(5)

                if not zip_url:
                    raise RuntimeError("Task done but no full_zip_url returned")

                # 4. 下载并解压
                zip_res = client.get(zip_url, timeout=60)
                zip_res.raise_for_status()

                with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
                    names = zf.namelist()
                    target = next((n for n in names if n.lower().endswith("/full.md") or n.lower() == "full.md"), None)
                    if not target:
                        target = next((n for n in names if n.lower().endswith(".md")), None)
                    if not target:
                        raise RuntimeError("No markdown file found in result zip")

                    md_bytes = zf.read(target)
                    md_text = md_bytes.decode("utf-8", errors="replace")

                duration_ms = round((time.monotonic() - start) * 1000)
                logger.info(
                    "mineru_parse_success",
                    path=str(pdf_path),
                    quality=ParseQuality.FULL,
                    duration_ms=duration_ms,
                )
                return ParsedDocument(
                    title=pdf_path.stem,
                    abstract="",
                    sections=[
                        ParsedSection(heading="Full Text", level=1, content=md_text),
                    ],
                    quality=ParseQuality.FULL,
                )

        except Exception as e:
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.warning(
                "mineru_api_error_fallback",
                path=str(pdf_path),
                error=str(e),
                duration_ms=duration_ms,
            )
            return FallbackParser().parse(pdf_path)


class FallbackParser:
    """PyMuPDF 纯文本 fallback 解析器。"""

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """降级解析: 仅提取纯文本。"""
        if fitz is None:
            raise ImportError("PyMuPDF (fitz) is not installed")

        start = time.monotonic()
        logger.info("fallback_parse_start", path=str(pdf_path))
        doc = fitz.open(str(pdf_path))
        text_parts: list[str] = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()

        full_text = "\n".join(text_parts)
        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "fallback_parse_complete",
            path=str(pdf_path),
            quality=ParseQuality.DEGRADED,
            pages=len(text_parts),
            duration_ms=duration_ms,
        )
        return ParsedDocument(
            title=pdf_path.stem,
            abstract="",
            sections=[
                ParsedSection(heading="Full Text", level=1, content=full_text),
            ],
            quality=ParseQuality.DEGRADED,
        )
