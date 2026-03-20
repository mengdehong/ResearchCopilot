"""E2E: Workspace CRUD 端点验证。"""

import uuid

import httpx
import pytest

from tests.e2e.seed import SeedData

pytestmark = pytest.mark.e2e


async def test_create_workspace(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/workspaces — 创建 workspace。"""
    response = await test_client.post(
        "/api/workspaces",
        headers=auth_headers,
        json={"name": "E2E New Workspace", "discipline": "physics"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "E2E New Workspace"
    assert data["discipline"] == "physics"
    assert "id" in data


async def test_list_workspaces(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/workspaces — 列表应只包含自己的 workspace。"""
    response = await test_client.get(
        "/api/workspaces",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # 至少包含种子数据的 workspace
    ids = [item["id"] for item in data]
    assert str(seed_data.workspace_id) in ids


async def test_get_workspace(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/workspaces/{id} — 获取详情。"""
    response = await test_client.get(
        f"/api/workspaces/{seed_data.workspace_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(seed_data.workspace_id)
    assert data["name"] == "E2E Test Workspace"


async def test_get_workspace_not_found(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/workspaces/{id} — 不存在的 ID 返回 404。"""
    fake_id = uuid.uuid4()
    response = await test_client.get(
        f"/api/workspaces/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_update_workspace(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """PUT /api/workspaces/{id} — 更新名称。"""
    response = await test_client.put(
        f"/api/workspaces/{seed_data.workspace_id}",
        headers=auth_headers,
        json={"name": "E2E Updated Name", "discipline": "computer_science"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "E2E Updated Name"


async def test_get_workspace_summary(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/workspaces/{id}/summary — 摘要含统计信息。"""
    response = await test_client.get(
        f"/api/workspaces/{seed_data.workspace_id}/summary",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "workspace_id" in data
    assert "document_count" in data
    assert "doc_status_counts" in data


async def test_delete_workspace_then_get_returns_404(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """DELETE + GET — 软删除后不可访问。"""
    # 先创建一个临时 workspace
    create_resp = await test_client.post(
        "/api/workspaces",
        headers=auth_headers,
        json={"name": "E2E To Delete", "discipline": "math"},
    )
    assert create_resp.status_code == 201
    ws_id = create_resp.json()["id"]

    # 删除
    del_resp = await test_client.delete(
        f"/api/workspaces/{ws_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    # 再获取 → 404
    get_resp = await test_client.get(
        f"/api/workspaces/{ws_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404
