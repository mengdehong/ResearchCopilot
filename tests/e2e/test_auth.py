"""E2E: 认证端点验证。"""

import httpx
import pytest

pytestmark = pytest.mark.e2e

PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/workspaces"),
    ("POST", "/api/v1/workspaces"),
    ("GET", "/api/v1/workspaces/00000000-0000-0000-0000-000000000000"),
    ("GET", "/api/v1/documents?workspace_id=00000000-0000-0000-0000-000000000000"),
    ("GET", "/api/v1/agent/threads?workspace_id=00000000-0000-0000-0000-000000000000"),
    ("GET", "/api/v1/editor/draft/00000000-0000-0000-0000-000000000000"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_unauthenticated_request_returns_401(
    test_client: httpx.AsyncClient,
    method: str,
    path: str,
) -> None:
    """未携带 token 的请求应返回 401。"""
    response = await test_client.request(method, path)

    assert response.status_code == 401


async def test_invalid_token_returns_401(
    test_client: httpx.AsyncClient,
) -> None:
    """携带无效 token 应返回 401。"""
    headers = {"Authorization": "Bearer invalid-token-000"}
    response = await test_client.get("/api/v1/workspaces", headers=headers)

    assert response.status_code == 401


async def test_expired_token_returns_401(
    test_client: httpx.AsyncClient,
) -> None:
    """过期 token 应返回 401。"""
    import uuid
    from datetime import UTC, datetime, timedelta

    import jwt

    payload = {
        "sub": str(uuid.uuid4()),
        "exp": datetime.now(UTC) - timedelta(hours=1),  # 已过期
        "iat": datetime.now(UTC) - timedelta(hours=2),
    }
    from tests.e2e.conftest import _test_app

    settings = _test_app.state.settings
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    headers = {"Authorization": f"Bearer {token}"}
    response = await test_client.get("/api/v1/workspaces", headers=headers)

    assert response.status_code == 401
