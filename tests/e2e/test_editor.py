"""E2E: Editor draft 端点验证。"""

import uuid

import httpx
import pytest

from tests.e2e.seed import SeedData

pytestmark = pytest.mark.e2e


async def _create_thread(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
    title: str = "Draft Thread",
) -> str:
    """Helper: 创建 thread 并返回 thread_id。"""
    resp = await client.post(
        "/api/v1/agent/threads",
        headers=headers,
        params={"workspace_id": workspace_id, "title": title},
    )
    assert resp.status_code == 201
    return resp.json()["thread_id"]


async def test_save_and_load_draft(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """PUT + GET /api/editor/draft — 保存并加载 draft。"""
    thread_id = await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Draft Test Thread",
    )

    # save_draft: thread_id 是 query param，content 是 str
    save_resp = await test_client.put(
        "/api/v1/editor/draft",
        headers=auth_headers,
        params={"thread_id": thread_id},
        json={"content": "E2E draft content"},
    )
    assert save_resp.status_code == 200, f"save_draft: {save_resp.text}"
    save_data = save_resp.json()
    assert save_data["content"] == "E2E draft content"

    # load_draft
    load_resp = await test_client.get(
        f"/api/v1/editor/draft/{thread_id}",
        headers=auth_headers,
    )
    assert load_resp.status_code == 200
    load_data = load_resp.json()
    assert load_data["content"] == "E2E draft content"


async def test_update_draft(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """保存 → 更新 → 加载 — 确认最新内容。"""
    thread_id = await _create_thread(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Draft Update Thread",
    )

    # v1
    await test_client.put(
        "/api/v1/editor/draft",
        headers=auth_headers,
        params={"thread_id": thread_id},
        json={"content": "v1"},
    )

    # v2
    await test_client.put(
        "/api/v1/editor/draft",
        headers=auth_headers,
        params={"thread_id": thread_id},
        json={"content": "v2"},
    )

    load_resp = await test_client.get(
        f"/api/v1/editor/draft/{thread_id}",
        headers=auth_headers,
    )
    assert load_resp.status_code == 200
    assert load_resp.json()["content"] == "v2"


async def test_load_draft_not_found(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/editor/draft/{thread_id} — 不存在的 draft 返回 404。"""
    fake_thread_id = uuid.uuid4()

    response = await test_client.get(
        f"/api/v1/editor/draft/{fake_thread_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
