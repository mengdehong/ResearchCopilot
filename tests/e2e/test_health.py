"""E2E: Health check 端点验证。"""

import httpx
import pytest

pytestmark = pytest.mark.e2e


async def test_health_endpoint(e2e_client: httpx.AsyncClient) -> None:
    """GET /api/health 应返回 200 + {"status": "ok"}。"""
    response = await e2e_client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_metrics_endpoint(e2e_client: httpx.AsyncClient) -> None:
    """GET /metrics 应返回 Prometheus 格式的指标数据。"""
    response = await e2e_client.get("/metrics")

    assert response.status_code == 200
    assert "http_request" in response.text or "process_" in response.text
