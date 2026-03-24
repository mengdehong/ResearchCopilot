"""异常体系测试。"""

from backend.core.exceptions import (
    AppError,
    ForbiddenError,
    LLMServiceError,
    NotFoundError,
    QuotaExceededError,
    SandboxError,
)


def test_app_error_defaults() -> None:
    err = AppError()
    assert err.status_code == 500
    assert err.error_code == "INTERNAL_ERROR"


def test_not_found_error() -> None:
    err = NotFoundError(message="Document not found")
    assert err.status_code == 404
    assert err.error_code == "NOT_FOUND"
    assert err.message == "Document not found"


def test_forbidden_error() -> None:
    err = ForbiddenError()
    assert err.status_code == 403


def test_quota_exceeded_error() -> None:
    err = QuotaExceededError()
    assert err.status_code == 429
    assert err.error_code == "QUOTA_EXCEEDED"


def test_sandbox_error() -> None:
    err = SandboxError(message="Docker daemon unavailable")
    assert err.status_code == 502
    assert err.error_code == "SANDBOX_ERROR"
    assert err.message == "Docker daemon unavailable"
    assert isinstance(err, AppError)


def test_llm_service_error() -> None:
    err = LLMServiceError(message="All providers down")
    assert err.status_code == 502
    assert err.error_code == "LLM_UNAVAILABLE"
    assert err.message == "All providers down"
    assert isinstance(err, AppError)


def test_llm_unavailable_is_subclass() -> None:
    """LLMUnavailableError in llm_gateway inherits from LLMServiceError."""
    from backend.services.llm_gateway import LLMUnavailableError

    assert issubclass(LLMUnavailableError, LLMServiceError)

