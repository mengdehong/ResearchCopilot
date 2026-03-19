"""Logger 测试。"""
import logging

import backend.core.logger as logger_module
from backend.core.logger import setup_logging


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


def test_sanitize_sensitive_fields() -> None:
    """敏感字段的值应被替换为 '***'。"""
    from backend.core.logger import sanitize_sensitive_fields

    event = {
        "event": "test",
        "openai_api_key": "sk-secret-123",
        "jwt_token": "eyJhbGci...",
        "user_password": "hunter2",
        "authorization": "Bearer xxx",
        "username": "alice",
    }
    result = sanitize_sensitive_fields(None, "info", event)

    assert result["openai_api_key"] == "***"
    assert result["jwt_token"] == "***"
    assert result["user_password"] == "***"
    assert result["authorization"] == "***"
    assert result["username"] == "alice"  # 非敏感字段不受影响
