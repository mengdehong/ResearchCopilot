"""E2E 测试共享 fixtures。

基于完整 Docker Compose 环境的端到端测试。
运行前需确保 `docker compose up -d` 已启动所有服务。
"""

from collections.abc import AsyncGenerator

import httpx
import pytest


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    """E2E 测试的 API base URL。"""
    return "http://localhost:8000"


@pytest.fixture(scope="session")
async def e2e_client(e2e_base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """创建 session 级别的 httpx 异步客户端。"""
    async with httpx.AsyncClient(
        base_url=e2e_base_url,
        timeout=httpx.Timeout(30.0),
    ) as client:
        yield client


@pytest.fixture(scope="session")
async def auth_token(e2e_client: httpx.AsyncClient) -> str:
    """获取测试用 JWT token。

    调用 /api/auth/dev-token 获取开发环境 token。
    如果端点不存在，跳过需要认证的测试。
    """
    response = await e2e_client.post("/api/auth/dev-token")
    if response.status_code != 200:
        pytest.skip("Dev token endpoint not available")
    return response.json()["access_token"]


@pytest.fixture(scope="session")
async def auth_client(
    e2e_base_url: str, auth_token: str
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """带认证 header 的 httpx 客户端。"""
    async with httpx.AsyncClient(
        base_url=e2e_base_url,
        timeout=httpx.Timeout(30.0),
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as client:
        yield client
