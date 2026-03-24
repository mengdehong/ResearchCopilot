"""PDF 解析引擎。封装 MinerU 和 PyMuPDF fallback。"""

import io
import re
import time
import zipfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import httpx

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


# ---------------------------------------------------------------------------
# MinerU API 纯函数
# ---------------------------------------------------------------------------


def _build_headers(api_key: str, user_token: str = "") -> dict[str, str]:
    """构造 MinerU API 请求头。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    if user_token:
        headers["token"] = user_token
    return headers


def _raise_api_error(resp_data: dict[str, Any], prefix: str) -> None:
    """根据 API 响应抛出详细错误。"""
    code = resp_data.get("code")
    msg = resp_data.get("msg", "")
    trace_id = resp_data.get("trace_id", "")
    raise RuntimeError(f"{prefix} failed: code={code}, msg={msg}, trace_id={trace_id}")


def _request_upload_url(
    client: httpx.Client,
    api_url: str,
    api_key: str,
    user_token: str,
    file_name: str,
    model_version: str,
    timeout: int,
) -> tuple[str, str]:
    """请求文件上传地址，返回 (batch_id, upload_url)。"""
    url = f"{api_url}/file-urls/batch"
    payload = {
        "files": [{"name": file_name}],
        "model_version": model_version,
    }
    res = client.post(
        url,
        headers=_build_headers(api_key, user_token),
        json=payload,
        timeout=timeout,
    )
    try:
        data = res.json()
    except Exception:
        data = {"code": res.status_code, "msg": res.text, "trace_id": ""}

    if res.status_code != 200 or data.get("code") != 0:
        _raise_api_error(data, "Request upload URL")

    result = data.get("data", {})
    batch_id = result.get("batch_id")
    file_urls = result.get("file_urls") or result.get("files") or []
    if not batch_id or not file_urls:
        raise RuntimeError(f"Unexpected upload URL response: {data}")
    return str(batch_id), str(file_urls[0])


def _upload_file(
    client: httpx.Client,
    upload_url: str,
    pdf_path: Path,
    timeout: int,
) -> None:
    """PUT 上传 PDF 文件到预签名 URL。"""
    with pdf_path.open("rb") as f:
        res = client.put(upload_url, content=f.read(), timeout=timeout)
        res.raise_for_status()


def _poll_batch_result(
    client: httpx.Client,
    api_url: str,
    api_key: str,
    user_token: str,
    batch_id: str,
    poll_timeout: int,
    poll_interval: int,
    request_timeout: int,
) -> dict[str, Any]:
    """轮询批量提取结果，返回完成后的任务 item。"""
    url = f"{api_url}/extract-results/batch/{batch_id}"
    start = time.time()

    while True:
        if poll_timeout > 0 and time.time() - start > poll_timeout:
            raise TimeoutError(f"MinerU task polling timed out after {poll_timeout}s")

        res = client.get(
            url,
            headers=_build_headers(api_key, user_token),
            timeout=request_timeout,
        )
        try:
            body = res.json()
        except Exception:
            body = {"code": res.status_code, "msg": res.text, "trace_id": ""}

        if res.status_code != 200 or body.get("code") != 0:
            _raise_api_error(body, "Query batch result")

        extract_result = body.get("data", {}).get("extract_result", [])
        extract_items = [extract_result] if isinstance(extract_result, dict) else extract_result

        if extract_items:
            item = extract_items[0]
            state = item.get("state", "")
            if state == "done":
                return item
            if state == "failed":
                raise RuntimeError(f"MinerU task failed: {item.get('err_msg', '')}")
            if state in {"waiting-file", "pending", "running", "converting"}:
                time.sleep(poll_interval)
                continue
            raise RuntimeError(f"Unknown MinerU task state: {state}")

        time.sleep(poll_interval)


def _download_and_extract_md(
    client: httpx.Client,
    zip_url: str,
    timeout: int,
) -> str:
    """下载结果 ZIP 并提取 full.md 内容，返回 Markdown 文本。"""
    res = client.get(zip_url, timeout=timeout)
    res.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        names = zf.namelist()
        target = next(
            (n for n in names if n.lower().endswith("/full.md") or n.lower() == "full.md"),
            None,
        )
        if not target:
            target = next((n for n in names if n.lower().endswith(".md")), None)
        if not target:
            raise RuntimeError("No markdown file found in result zip")

        return zf.read(target).decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 论文参考文献裁剪（Paper Mode）
# ---------------------------------------------------------------------------


def _is_ref_heading(line: str) -> bool:
    """判断一行是否为参考文献标题。"""
    s = line.strip()
    if not s:
        return False
    pattern = (
        r"^(?:#{1,6}\s*)?"
        r"(?:\d+[\.\)]\s*)?"
        r"(references|bibliography|works\s+cited|reference|参考文献|参考资料)"
        r"\s*[:：]?$"
    )
    return re.match(pattern, s, flags=re.IGNORECASE) is not None


def _count_heading_hits(md_text: str, words: list[str]) -> int:
    """统计 Markdown 文本中匹配指定标题关键词的数量。"""
    count = 0
    for line in md_text.splitlines():
        s = line.strip().lower()
        if not s:
            continue
        normalized = re.sub(r"^(?:#{1,6}\s*)?(?:\d+[\.\)]\s*)?", "", s)
        if normalized in words:
            count += 1
    return count


def _looks_like_paper(md_text: str) -> bool:
    """启发式判断 Markdown 内容是否为学术论文。"""
    lines = md_text.splitlines()
    has_ref_heading = any(_is_ref_heading(line) for line in lines)
    if not has_ref_heading:
        return False

    section_hits = _count_heading_hits(
        md_text,
        [
            "abstract",
            "introduction",
            "method",
            "methods",
            "methodology",
            "experiment",
            "experiments",
            "results",
            "discussion",
            "conclusion",
            "摘要",
            "引言",
            "方法",
            "实验",
            "结果",
            "结论",
        ],
    )
    citation_hits = len(re.findall(r"\[[0-9]{1,3}\]", md_text))
    return section_hits >= 2 or citation_hits >= 3


def trim_references_if_paper(md_text: str, paper_mode: str) -> tuple[str, bool, str]:
    """根据 paper_mode 裁剪参考文献部分。

    Args:
        md_text: Markdown 全文。
        paper_mode: ``auto`` | ``on`` | ``off``。

    Returns:
        (处理后文本, 是否裁剪, 裁剪原因)。
    """
    if paper_mode == "off":
        return md_text, False, "paper_mode=off"

    lines = md_text.splitlines()
    ref_idx = -1
    for i, line in enumerate(lines):
        if _is_ref_heading(line):
            ref_idx = i
            break

    if ref_idx < 0:
        return md_text, False, "no references heading"

    is_paper = paper_mode == "on" or (paper_mode == "auto" and _looks_like_paper(md_text))
    if not is_paper:
        return md_text, False, "not detected as paper"

    trimmed = "\n".join(lines[:ref_idx]).rstrip()
    return trimmed, True, "removed from references heading"


# ---------------------------------------------------------------------------
# MinerUParser — MinerU GPU 解析器
# ---------------------------------------------------------------------------


class MinerUParser:
    """MinerU GPU 解析器 (API 接入)。"""

    def __init__(
        self,
        *,
        api_url: str | None = None,
        api_key: str | None = None,
        user_token: str | None = None,
        model_version: str | None = None,
        paper_mode: str | None = None,
        poll_timeout: int | None = None,
        poll_interval: int | None = None,
        request_timeout: int | None = None,
    ) -> None:
        from backend.core.config import Settings

        settings = Settings()
        self._api_url = api_url or settings.mineru_api_url
        self._api_key = api_key or settings.mineru_api_key
        self._user_token = user_token or settings.mineru_user_token or ""
        self._model_version = model_version or settings.mineru_model_version
        self._paper_mode = paper_mode or settings.mineru_paper_mode
        self._poll_timeout = (
            poll_timeout if poll_timeout is not None else settings.mineru_poll_timeout
        )
        self._poll_interval = (
            poll_interval if poll_interval is not None else settings.mineru_poll_interval
        )
        self._request_timeout = (
            request_timeout if request_timeout is not None else settings.mineru_request_timeout
        )

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """调用 MinerU HTTP API 解析 PDF 为结构化文档。"""
        start = time.monotonic()
        logger.info("mineru_parse_start", path=str(pdf_path))

        if not self._api_key:
            logger.warning("mineru_no_api_key_fallback", path=str(pdf_path))
            return FallbackParser().parse(pdf_path)

        try:
            with httpx.Client() as client:
                batch_id, upload_url = _request_upload_url(
                    client=client,
                    api_url=self._api_url,
                    api_key=self._api_key,
                    user_token=self._user_token,
                    file_name=pdf_path.name,
                    model_version=self._model_version,
                    timeout=self._request_timeout,
                )

                _upload_file(
                    client=client,
                    upload_url=upload_url,
                    pdf_path=pdf_path,
                    timeout=self._request_timeout,
                )

                item = _poll_batch_result(
                    client=client,
                    api_url=self._api_url,
                    api_key=self._api_key,
                    user_token=self._user_token,
                    batch_id=batch_id,
                    poll_timeout=self._poll_timeout,
                    poll_interval=self._poll_interval,
                    request_timeout=self._request_timeout,
                )

                zip_url = item.get("full_zip_url", "")
                if not zip_url:
                    raise RuntimeError(f"Task done but no full_zip_url returned: {item}")

                md_text = _download_and_extract_md(
                    client=client,
                    zip_url=zip_url,
                    timeout=self._request_timeout,
                )

            # 论文参考文献裁剪
            md_text, trimmed, trim_reason = trim_references_if_paper(md_text, self._paper_mode)
            if trimmed:
                logger.info("paper_mode_trim_applied", reason=trim_reason)

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
