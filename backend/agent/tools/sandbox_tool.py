"""沙盒代码执行 Tool — 封装 DockerExecutor。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from backend.core.config import get_settings
from backend.core.logger import get_logger
from backend.services.sandbox_manager import DockerExecutor, ExecutionRequest

logger = get_logger(__name__)


def _get_executor() -> DockerExecutor:
    """懒初始化 DockerExecutor 单例（从 Settings 读取配置）。"""
    cfg = get_settings()
    return DockerExecutor(
        image=cfg.sandbox_image,
        memory_limit=cfg.sandbox_memory_limit,
        cpu_count=cfg.sandbox_cpu_count,
    )


@tool
def execute_code(code: str, language: str = "python") -> dict[str, Any]:
    """Execute code in a sandboxed environment.

    Args:
        code: Source code to execute.
        language: Programming language (default: python).

    Returns:
        Dictionary with stdout, stderr, exit_code, artifacts.
    """
    logger.info("sandbox_execute", language=language, code_length=len(code))

    cfg = get_settings()
    executor = _get_executor()
    request = ExecutionRequest(code=code, timeout_seconds=cfg.sandbox_timeout_seconds)
    result = executor.execute(request)

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "artifacts": list(result.output_files.keys()),
        "duration_ms": round(result.duration_seconds * 1000),
    }
