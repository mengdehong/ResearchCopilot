"""结构化日志配置。基于 structlog，支持 trace_id 串联请求链路、敏感字段脱敏。"""
import logging
import re
import sys
from typing import Any

import structlog

_logging_configured = False


def setup_logging(*, debug: bool = False) -> None:
    """初始化 structlog 配置。应用启动时调用一次，重复调用安全（幂等）。"""
    global _logging_configured  # noqa: PLW0603
    if _logging_configured:
        return
    _logging_configured = True

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        sanitize_sensitive_fields,
    ]

    if debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取结构化 logger 实例。"""
    return structlog.get_logger(name)


_SENSITIVE_PATTERN = re.compile(
    r"(api_key|secret|token|password|jwt|authorization)",
    re.IGNORECASE,
)


def sanitize_sensitive_fields(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """将结构化日志中的敏感字段值替换为 '***'。"""
    for key in event_dict:
        if _SENSITIVE_PATTERN.search(key):
            event_dict[key] = "***"
    return event_dict
