"""HTTP middleware: trace ID propagation + structured access logging."""
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logger import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate X-Trace-ID for every request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
        request.state.trace_id = trace_id

        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id

        structlog.contextvars.unbind_contextvars("trace_id")
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Structured access log: method, path, status_code, duration_ms."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "access_log",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
