"""E2E: 认证拦截验证。"""

import httpx
import pytest

pytestmark = pytest.mark.e2e

# 需要认证的端点列表
PROTECTED_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/workspaces"),
    ("POST", "/api/workspaces"),
    ("GET", "/api/workspaces/00000000-0000-0000-0000-000000000000"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_unauthenticated_request_returns_401(
    e2e_client: httpx.AsyncClient,
    method: str,
    path: str,
) -> None:
    """未携带 token 的请求应返回 401。"""
    response = await e2e_client.request(method, path)

    assert response.status_code == 401
