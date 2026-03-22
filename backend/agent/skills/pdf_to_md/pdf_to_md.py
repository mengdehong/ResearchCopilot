"""pdf_to_md Skill 实现。

通过 MinerU v4 API 将本地 PDF 文件转为高质量 Markdown。
复用 parser_engine 中的纯函数，支持 paper_mode 参考文献裁剪。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from backend.agent.skills.base import SkillDefinition
from backend.core.config import Settings
from backend.core.logger import get_logger
from backend.services.parser_engine import (
    _download_and_extract_md,
    _poll_batch_result,
    _request_upload_url,
    _upload_file,
    trim_references_if_paper,
)

logger = get_logger(__name__)


def _execute(
    pdf_path: str,
    output_path: str,
    model_version: str = "",
    paper_mode: str = "",
) -> dict[str, Any]:
    """将 PDF 文件通过 MinerU API 转换为 Markdown 并写入文件。

    Args:
        pdf_path: 待转换的 PDF 文件路径。
        output_path: 输出 Markdown 文件路径。
        model_version: MinerU 模型版本，留空使用配置默认值。
        paper_mode: 参考文献裁剪模式，留空使用配置默认值。

    Returns:
        包含 ``md_path``、``char_count``、``trimmed`` 的结果字典。
    """
    settings = Settings()

    input_path = Path(pdf_path).expanduser().resolve()
    out_path = Path(output_path).expanduser().resolve()

    api_key = settings.mineru_api_key
    if not api_key:
        raise ValueError("MINERU_API_KEY is required. Set it in .env or environment.")

    if not input_path.exists() or not input_path.is_file():
        raise ValueError(f"Input file not found: {input_path}")
    if input_path.suffix.lower() != ".pdf":
        raise ValueError(f"Input file must be a PDF: {input_path}")

    api_url = settings.mineru_api_url
    user_token = settings.mineru_user_token or ""
    mv = model_version or settings.mineru_model_version
    pm = paper_mode or settings.mineru_paper_mode
    request_timeout = settings.mineru_request_timeout

    logger.info("pdf_to_md_start", input=str(input_path), output=str(out_path))

    with httpx.Client() as client:
        batch_id, upload_url = _request_upload_url(
            client=client,
            api_url=api_url,
            api_key=api_key,
            user_token=user_token,
            file_name=input_path.name,
            model_version=mv,
            timeout=request_timeout,
        )

        _upload_file(
            client=client,
            upload_url=upload_url,
            pdf_path=input_path,
            timeout=request_timeout,
        )

        item = _poll_batch_result(
            client=client,
            api_url=api_url,
            api_key=api_key,
            user_token=user_token,
            batch_id=batch_id,
            poll_timeout=settings.mineru_poll_timeout,
            poll_interval=settings.mineru_poll_interval,
            request_timeout=request_timeout,
        )

        zip_url = item.get("full_zip_url", "")
        if not zip_url:
            raise RuntimeError(f"Task done but no full_zip_url returned: {item}")

        md_text = _download_and_extract_md(
            client=client,
            zip_url=zip_url,
            timeout=request_timeout,
        )

    md_text, trimmed, trim_reason = trim_references_if_paper(md_text, pm)
    if trimmed:
        logger.info("paper_mode_trim_applied", reason=trim_reason)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md_text + "\n", encoding="utf-8")

    logger.info("pdf_to_md_done", md_path=str(out_path), chars=len(md_text), trimmed=trimmed)

    return {
        "md_path": str(out_path),
        "char_count": len(md_text),
        "trimmed": trimmed,
    }


PDF_TO_MD_SKILL = SkillDefinition(
    name="pdf_to_md",
    description=(
        "Convert a local PDF file to high-quality Markdown via MinerU v4 API. "
        "Supports automatic reference trimming for academic papers (paper_mode)."
    ),
    input_schema={
        "pdf_path": "str — absolute path to the PDF file",
        "output_path": "str — absolute path for the output Markdown file",
        "model_version": "str (optional) — 'pipeline' | 'vlm' | 'MinerU-HTML' (default: from config)",
        "paper_mode": "str (optional) — 'auto' | 'on' | 'off' (default: from config)",
    },
    output_schema={
        "md_path": "str — absolute path of the generated Markdown file",
        "char_count": "int — character count of the output Markdown",
        "trimmed": "bool — whether references section was trimmed",
    },
    tags=["pdf", "markdown", "conversion", "mineru", "paper"],
    execute=_execute,
)
