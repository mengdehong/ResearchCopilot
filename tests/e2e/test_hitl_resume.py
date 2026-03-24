"""HITL Resume API E2E 测试。

验证 POST /{thread_id}/runs/{run_id}/resume 完整链路：
  1. select_papers resume approve（传 selected_ids）
  2. confirm_execute resume reject
  3. confirm_finalize resume with modified_markdown

使用 MockLangGraphRunner（已扩展 resume_run 方法）驱动。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import httpx

    from tests.e2e.mocks.mock_langgraph import MockLangGraphRunner
    from tests.e2e.seed import SeedData


async def _create_thread_and_run(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
) -> tuple[str, str]:
    """创建 thread + run，返回 (thread_id, run_id)。"""
    resp = await client.post(
        "/api/v1/agent/threads",
        headers=headers,
        params={"workspace_id": workspace_id, "title": "HITL Test Thread"},
    )
    assert resp.status_code == 201
    thread_id = resp.json()["thread_id"]

    resp = await client.post(
        f"/api/v1/agent/threads/{thread_id}/runs",
        headers=headers,
        json={"message": "test message"},
    )
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    return thread_id, run_id


@pytest.mark.asyncio
async def test_resume_approve_with_selected_ids(
    test_client: httpx.AsyncClient,
    seed_data: SeedData,
    auth_headers: dict[str, str],
    mock_lg_runner: MockLangGraphRunner,
) -> None:
    """select_papers → resume approve with selected_ids。

    验证：
    1. POST /resume 返回 202
    2. MockLangGraphRunner 记录了 resume_run 调用
    3. resume_payload 包含 action=approve 和 selected_ids
    """
    thread_id, run_id = await _create_thread_and_run(
        test_client, auth_headers, str(seed_data.workspace_id)
    )

    resume_body = {
        "action": "approve",
        "selected_ids": ["2401.00001", "2401.00002"],
    }

    resp = await test_client.post(
        f"/api/v1/agent/threads/{thread_id}/runs/{run_id}/resume",
        headers=auth_headers,
        json=resume_body,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["stream_url"]

    # 验证 MockLangGraphRunner 记录
    resume_calls = [c for c in mock_lg_runner.calls if c[0] == "resume_run"]
    assert len(resume_calls) >= 1
    last_resume = resume_calls[-1][1]
    assert last_resume["resume_payload"]["action"] == "approve"
    assert last_resume["resume_payload"]["selected_ids"] == ["2401.00001", "2401.00002"]


@pytest.mark.asyncio
async def test_resume_reject(
    test_client: httpx.AsyncClient,
    seed_data: SeedData,
    auth_headers: dict[str, str],
    mock_lg_runner: MockLangGraphRunner,
) -> None:
    """confirm_execute → resume reject。

    验证：
    1. POST /resume 返回 202
    2. resume_payload 包含 action=reject
    """
    thread_id, run_id = await _create_thread_and_run(
        test_client, auth_headers, str(seed_data.workspace_id)
    )

    resume_body = {"action": "reject"}

    resp = await test_client.post(
        f"/api/v1/agent/threads/{thread_id}/runs/{run_id}/resume",
        headers=auth_headers,
        json=resume_body,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"

    resume_calls = [c for c in mock_lg_runner.calls if c[0] == "resume_run"]
    last_resume = resume_calls[-1][1]
    assert last_resume["resume_payload"]["action"] == "reject"


@pytest.mark.asyncio
async def test_resume_finalize_with_modified_markdown(
    test_client: httpx.AsyncClient,
    seed_data: SeedData,
    auth_headers: dict[str, str],
    mock_lg_runner: MockLangGraphRunner,
) -> None:
    """confirm_finalize → resume with modified_markdown。

    验证：
    1. POST /resume 返回 202
    2. resume_payload 包含 modified_markdown 字段
    """
    thread_id, run_id = await _create_thread_and_run(
        test_client, auth_headers, str(seed_data.workspace_id)
    )

    edited_markdown = "# Modified Report\n\nUser-edited content here."
    resume_body = {
        "action": "approve",
        "payload": {"modified_markdown": edited_markdown},
    }

    resp = await test_client.post(
        f"/api/v1/agent/threads/{thread_id}/runs/{run_id}/resume",
        headers=auth_headers,
        json=resume_body,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"

    resume_calls = [c for c in mock_lg_runner.calls if c[0] == "resume_run"]
    last_resume = resume_calls[-1][1]
    assert last_resume["resume_payload"]["action"] == "approve"
    assert last_resume["resume_payload"]["modified_markdown"] == edited_markdown
