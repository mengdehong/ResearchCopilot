"""ArXiv PDF 下载器 — 从 ArXiv 下载论文 PDF 到本地存储。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from backend.core.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

_ARXIV_PDF_BASE = "https://arxiv.org/pdf"
_DOWNLOAD_TIMEOUT = 60.0


def download_arxiv_pdf(
    arxiv_id: str,
    storage_dir: Path,
) -> Path:
    """下载 ArXiv 论文 PDF 到指定存储目录。

    Args:
        arxiv_id: ArXiv 论文 ID（如 '2301.00001v1'）。
        storage_dir: 目标存储目录。

    Returns:
        下载后的 PDF 文件路径。

    Raises:
        httpx.HTTPStatusError: 下载失败（非 2xx）。
        httpx.TimeoutException: 下载超时。
    """
    clean_id = arxiv_id.strip().rstrip("/")
    pdf_url = f"{_ARXIV_PDF_BASE}/{clean_id}.pdf"

    storage_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = clean_id.replace("/", "_") + ".pdf"
    dest_path = storage_dir / safe_filename

    if dest_path.exists():
        logger.info("arxiv_pdf_cached", arxiv_id=arxiv_id, path=str(dest_path))
        return dest_path

    logger.info("arxiv_pdf_download_start", arxiv_id=arxiv_id, url=pdf_url)

    response = httpx.get(
        pdf_url,
        timeout=_DOWNLOAD_TIMEOUT,
        follow_redirects=True,
    )
    response.raise_for_status()

    dest_path.write_bytes(response.content)
    logger.info(
        "arxiv_pdf_download_done",
        arxiv_id=arxiv_id,
        path=str(dest_path),
        size_bytes=len(response.content),
    )
    return dest_path
