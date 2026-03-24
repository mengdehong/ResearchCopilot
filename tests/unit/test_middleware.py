"""中间件单元测试 -- RequestIDMiddleware + AccessLogMiddleware."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.middleware import AccessLogMiddleware, RequestIDMiddleware


@pytest.fixture
def test_app() -> FastAPI:
    """Create a minimal FastAPI app with middleware for testing."""
    app = FastAPI()

    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def _test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture
async def client(test_app: FastAPI) -> AsyncClient:
    """Create httpx AsyncClient for the test app."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# RequestIDMiddleware
# ---------------------------------------------------------------------------


class TestRequestIDMiddleware:
    async def test_response_contains_x_trace_id(self, client: AsyncClient) -> None:
        response = await client.get("/test")
        assert response.status_code == 200
        assert "x-trace-id" in response.headers
        trace_id = response.headers["x-trace-id"]
        # Should be a valid UUID-like string
        assert len(trace_id) == 36  # UUID format: 8-4-4-4-12

    async def test_trace_id_is_unique_per_request(self, client: AsyncClient) -> None:
        r1 = await client.get("/test")
        r2 = await client.get("/test")
        assert r1.headers["x-trace-id"] != r2.headers["x-trace-id"]

    async def test_uses_provided_trace_id(self, client: AsyncClient) -> None:
        custom_trace_id = "custom-trace-id-12345"
        response = await client.get(
            "/test",
            headers={"X-Trace-ID": custom_trace_id},
        )
        assert response.headers["x-trace-id"] == custom_trace_id


# ---------------------------------------------------------------------------
# AccessLogMiddleware
# ---------------------------------------------------------------------------


class TestAccessLogMiddleware:
    async def test_logs_request_info(self, client: AsyncClient) -> None:
        with patch("backend.api.middleware.logger") as mock_logger:
            response = await client.get("/test")
            assert response.status_code == 200

            # Should have called logger.info with access log
            mock_logger.info.assert_called()
            call_kwargs = mock_logger.info.call_args
            # Check that structured fields are present
            assert "method" in call_kwargs.kwargs or any(
                "method" in str(arg) for arg in call_kwargs.args
            )
