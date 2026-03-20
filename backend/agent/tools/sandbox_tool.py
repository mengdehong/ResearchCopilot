"""沙盒代码执行 Tool — 封装 SandboxManager.execute()。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from backend.core.logger import get_logger

logger = get_logger(__name__)


@tool
def execute_code(code: str, language: str = "python") -> dict[str, Any]:
    """Execute code in a sandboxed environment.

    Args:
        code: Source code to execute.
        language: Programming language (default: python).

    Returns:
        Dictionary with stdout, stderr, exit_code, artifacts.
    """
    # TODO: 接入真实 SandboxManager.execute()
    # MVP 阶段返回占位结果

    logger.info("sandbox_execute", language=language, code_length=len(code))

    return {
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "artifacts": [],
        "duration_ms": 0,
    }
