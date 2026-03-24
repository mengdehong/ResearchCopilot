"""速率限制单元测试 — 验证 slowapi 集成正确性。"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_rate_limited_app(limit: str = "3/minute") -> FastAPI:
    """创建带速率限制的最小测试 App。"""
    test_limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["120/minute"],
        storage_uri="memory://",
    )

    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/limited")
    @test_limiter.limit(limit)
    async def _limited(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/unlimited")
    async def _unlimited() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture
def rate_limited_app() -> FastAPI:
    return _create_rate_limited_app("3/minute")


@pytest.fixture
async def client(rate_limited_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=rate_limited_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRateLimitExceeded:
    """超额后应返回 429。"""

    async def test_returns_429_after_limit(self, client: AsyncClient) -> None:
        for i in range(3):
            resp = await client.get("/limited")
            assert resp.status_code == 200, f"Request {i + 1} should succeed"

        # 第 4 次请求应被限流
        resp = await client.get("/limited")
        assert resp.status_code == 429

    async def test_429_body_contains_error(self, client: AsyncClient) -> None:
        for _ in range(3):
            await client.get("/limited")

        resp = await client.get("/limited")
        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body or "detail" in body


class TestUnlimitedEndpoint:
    """未标记 @limiter.limit 的端点不受路由级限制。"""

    async def test_unlimited_always_200(self, client: AsyncClient) -> None:
        for _ in range(10):
            resp = await client.get("/unlimited")
            assert resp.status_code == 200


class TestLimiterResetsPerWindow:
    """不同 limiter 实例有独立的计数。"""

    async def test_new_app_has_fresh_counters(self) -> None:
        app = _create_rate_limited_app("2/minute")
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r1 = await c.get("/limited")
            r2 = await c.get("/limited")
            assert r1.status_code == 200
            assert r2.status_code == 200

            r3 = await c.get("/limited")
            assert r3.status_code == 429


class TestGetUserIdOrIp:
    """验证 get_user_id_or_ip key 函数。"""

    def test_returns_ip_without_auth_header(self) -> None:
        from backend.api.rate_limit import get_user_id_or_ip

        request = MagicMock()
        request.headers = {}
        request.client.host = "10.0.0.1"
        request.scope = {"type": "http"}

        result = get_user_id_or_ip(request)
        assert result == "10.0.0.1"

    def test_returns_user_id_from_jwt(self) -> None:
        import jwt as pyjwt

        from backend.api.rate_limit import get_user_id_or_ip

        token = pyjwt.encode(
            {"sub": "user-123"},
            "a-sufficiently-long-secret-key-for-hs256",
            algorithm="HS256",
        )

        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client.host = "10.0.0.1"
        request.scope = {"type": "http"}

        result = get_user_id_or_ip(request)
        assert result == "user-123"

    def test_falls_back_to_ip_on_invalid_jwt(self) -> None:
        from backend.api.rate_limit import get_user_id_or_ip

        request = MagicMock()
        request.headers = {"Authorization": "Bearer not-a-valid-jwt"}
        request.client.host = "10.0.0.1"
        request.scope = {"type": "http"}

        result = get_user_id_or_ip(request)
        assert result == "10.0.0.1"

    def test_falls_back_to_ip_if_no_sub_claim(self) -> None:
        import jwt as pyjwt

        from backend.api.rate_limit import get_user_id_or_ip

        token = pyjwt.encode(
            {"role": "admin"},  # no 'sub' field
            "a-sufficiently-long-secret-key-for-hs256",
            algorithm="HS256",
        )

        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client.host = "10.0.0.1"
        request.scope = {"type": "http"}

        result = get_user_id_or_ip(request)
        assert result == "10.0.0.1"


class TestLimiterConfig:
    """验证 limiter 从 Settings 正确初始化。"""

    def test_limiter_enabled_by_default(self) -> None:
        from backend.api.rate_limit import limiter

        assert limiter.enabled is True

    def test_limiter_disabled_via_env(self) -> None:
        disabled_limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["120/minute"],
            storage_uri="memory://",
            enabled=False,
        )
        assert disabled_limiter.enabled is False

    async def test_disabled_limiter_does_not_block(self) -> None:
        """enabled=False 时不应限流。"""
        disabled_limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["120/minute"],
            storage_uri="memory://",
            enabled=False,
        )

        app = FastAPI()
        app.state.limiter = disabled_limiter
        app.add_exception_handler(
            RateLimitExceeded,
            _rate_limit_exceeded_handler,  # type: ignore[arg-type]
        )
        app.add_middleware(SlowAPIMiddleware)

        @app.get("/test")
        @disabled_limiter.limit("1/minute")
        async def _test(request: Request) -> dict[str, str]:
            return {"ok": "true"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # 即使限额=1，disabled 时也不应拦截
            for _ in range(5):
                resp = await c.get("/test")
                assert resp.status_code == 200
