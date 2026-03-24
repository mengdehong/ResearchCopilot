"""E2E: Agent 端点验证。"""

import httpx
import pytest

from tests.e2e.mocks.mock_langgraph import MockLangGraphRunner
from tests.e2e.seed import SeedData

pytestmark = pytest.mark.e2e


async def _create_thread(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
    title: str = "Test Thread",
) -> str:
    """Helper: 创建 thread 并返回 thread_id。"""
    resp = await client.post(
        "/api/v1/agent/threads",
        headers=headers,
        params={"workspace_id": workspace_id, "title": title},
    )
    assert resp.status_code == 201, f"create_thread failed: {resp.text}"
    return resp.json()["thread_id"]


async def test_create_thread(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """POST /api/agent/threads — 创建 thread。"""
    response = await test_client.post(
        "/api/v1/agent/threads",
        headers=auth_headers,
        params={
            "workspace_id": str(seed_data.workspace_id),
            "title": "E2E Test Thread",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "thread_id" in data
    assert data["title"] == "E2E Test Thread"


async def test_list_threads(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/agent/threads?workspace_id=... — 列出 threads。"""
    await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "List Test Thread",
    )

    response = await test_client.get(
        "/api/v1/agent/threads",
        headers=auth_headers,
        params={"workspace_id": str(seed_data.workspace_id)},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_thread(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/agent/threads/{id} — 获取 thread 详情。"""
    thread_id = await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Get Test Thread",
    )

    response = await test_client.get(
        f"/api/v1/agent/threads/{thread_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"] == thread_id


async def test_delete_thread(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """DELETE /api/agent/threads/{id} — 删除后 GET 返回 404。"""
    thread_id = await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Delete Test Thread",
    )

    del_resp = await test_client.delete(
        f"/api/v1/agent/threads/{thread_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    get_resp = await test_client.get(
        f"/api/v1/agent/threads/{thread_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404


async def test_create_run(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
    mock_lg_runner: MockLangGraphRunner,
) -> None:
    """POST /api/agent/threads/{id}/runs — 创建 run (202 Accepted)。"""
    thread_id = await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Run Test Thread",
    )

    response = await test_client.post(
        f"/api/v1/agent/threads/{thread_id}/runs",
        headers=auth_headers,
        json={"message": "请帮我搜索量子计算论文"},
    )

    assert response.status_code == 202, f"create_run: {response.text}"
    data = response.json()
    assert "run_id" in data
    assert "status" in data


async def test_list_runs(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
    mock_lg_runner: MockLangGraphRunner,
) -> None:
    """GET /api/agent/threads/{id}/runs — 列出 runs。"""
    thread_id = await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "List Runs Thread",
    )

    # 先创建一个 run
    create_resp = await test_client.post(
        f"/api/v1/agent/threads/{thread_id}/runs",
        headers=auth_headers,
        json={"message": "test"},
    )
    assert create_resp.status_code == 202, f"create_run: {create_resp.text}"

    response = await test_client.get(
        f"/api/v1/agent/threads/{thread_id}/runs",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_stream_run_events(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
    mock_lg_runner: MockLangGraphRunner,
) -> None:
    """GET /api/agent/threads/{id}/runs/{run_id}/events — SSE 事件流。"""
    thread_id = await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Stream Test Thread",
    )

    run_resp = await test_client.post(
        f"/api/v1/agent/threads/{thread_id}/runs",
        headers=auth_headers,
        json={"message": "test stream"},
    )
    assert run_resp.status_code == 202, f"create_run: {run_resp.text}"
    run_id = run_resp.json()["run_id"]

    response = await test_client.get(
        f"/api/v1/agent/threads/{thread_id}/runs/{run_id}/stream",
        headers=auth_headers,
    )

    assert response.status_code == 200
