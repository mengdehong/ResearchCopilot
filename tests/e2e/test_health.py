"""E2E: Health check 端点验证。"""

import httpx
import pytest

pytestmark = pytest.mark.e2e


async def test_health_endpoint(test_client: httpx.AsyncClient) -> None:
    """GET /api/health 应返回 200 + {"status": "ok"}。"""
    response = await test_client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
