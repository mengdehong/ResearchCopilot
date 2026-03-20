"""异常体系测试。"""

from backend.core.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
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
