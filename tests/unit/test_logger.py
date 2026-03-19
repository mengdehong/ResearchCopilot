"""Logger 测试。"""
import logging

from backend.core.logger import setup_logging, _logging_configured
import backend.core.logger as logger_module


def test_setup_logging_idempotent() -> None:
    """重复调用 setup_logging() 不应重复添加 handler。"""
    # 重置状态
    original = logger_module._logging_configured
    logger_module._logging_configured = False
    root = logging.getLogger()
    original_handler_count = len(root.handlers)

    try:
        setup_logging(debug=True)
        count_after_first = len(root.handlers)

        setup_logging(debug=True)
        count_after_second = len(root.handlers)

        assert count_after_second == count_after_first, (
            f"Handler count changed: {count_after_first} -> {count_after_second}"
        )
    finally:
        # 清理本次测试添加的 handler
        while len(root.handlers) > original_handler_count:
            root.handlers.pop()
        logger_module._logging_configured = original
