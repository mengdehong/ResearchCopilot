"""沙盒代码执行 Tool — 封装 DockerExecutor。"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from backend.core.config import get_settings
from backend.core.logger import get_logger
from backend.services.sandbox_manager import DockerExecutor, ExecutionRequest

logger = get_logger(__name__)

_IMAGE_EXTS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".svg"})


def _get_executor() -> DockerExecutor:
    """懒初始化 DockerExecutor 单例（从 Settings 读取配置）。"""
    cfg = get_settings()
    return DockerExecutor(
        image=cfg.sandbox_image,
        memory_limit=cfg.sandbox_memory_limit,
        cpu_count=cfg.sandbox_cpu_count,
    )


def _encode_images(output_files: dict[str, bytes]) -> list[dict[str, str]]:
    """将图片类输出文件 base64 编码，返回 {name, data} 列表。"""
    return [
        {"name": name, "data": base64.b64encode(content).decode()}
        for name, content in output_files.items()
        if Path(name).suffix.lower() in _IMAGE_EXTS
    ]


@tool
def execute_code(code: str, language: str = "python") -> dict[str, Any]:
    """Execute code in a sandboxed environment.

    Args:
        code: Source code to execute.
        language: Programming language (default: python).

    Returns:
        Dictionary with stdout, stderr, exit_code, artifacts, images, duration_ms.
        images: list of {name, data} where data is base64-encoded image content.
    """
    logger.info("sandbox_execute", language=language, code_length=len(code))

    cfg = get_settings()
    executor = _get_executor()
    request = ExecutionRequest(code=code, timeout_seconds=cfg.sandbox_timeout_seconds)
    result = executor.execute(request)

    images = _encode_images(result.output_files)
    logger.info(
        "sandbox_output_files",
        total=len(result.output_files),
        images=len(images),
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "artifacts": list(result.output_files.keys()),
        "images": images,
        "duration_ms": round(result.duration_seconds * 1000),
    }
