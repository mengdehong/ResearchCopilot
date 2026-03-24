"""自定义异常类型与全局异常处理器。"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常基类。"""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "Access denied"


class QuotaExceededError(AppError):
    status_code = 429
    error_code = "QUOTA_EXCEEDED"
    message = "Monthly token quota exceeded"


class LangGraphUnavailableError(AppError):
    status_code = 502
    error_code = "AGENT_UNAVAILABLE"
    message = "Agent service is temporarily unavailable"


class InvalidStateTransitionError(AppError):
    status_code = 409
    error_code = "INVALID_STATE"
    message = "Invalid state transition for this resource"


class UploadNotFoundError(AppError):
    status_code = 400
    error_code = "UPLOAD_NOT_FOUND"
    message = "File not found in storage after upload"


class SandboxError(AppError):
    """沙箱执行服务错误（Docker 不可用/操作失败）。"""

    status_code = 502
    error_code = "SANDBOX_ERROR"
    message = "Code execution service error"


class LLMServiceError(AppError):
    """所有 LLM Provider 均不可用。"""

    status_code = 502
    error_code = "LLM_UNAVAILABLE"
    message = "LLM service is temporarily unavailable"


class RunNotActiveError(AppError):
    """Run 不处于活跃状态，无法暂停或终止。"""

    status_code = 409
    error_code = "RUN_NOT_ACTIVE"
    message = "Run is not in an active state"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """全局异常处理器。挂载到 FastAPI app。"""
    trace_id = getattr(request.state, "trace_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail": exc.message,
            "trace_id": trace_id,
        },
    )
