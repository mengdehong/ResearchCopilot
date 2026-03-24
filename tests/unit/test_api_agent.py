"""Agent router tests — mock agent_service and LangGraphRunner."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import (
    get_current_user,
    get_current_user_or_system,
    get_current_user_sse,
    get_db,
    get_lg_runner,
)
from backend.api.routers import agent as agent_router
from backend.main import app
from backend.models.user import User


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.external_id = "ext"
    u.email = "a@b.com"
    u.display_name = "Test"
    u.settings = {}
    u.created_at = u.updated_at = datetime.now(tz=UTC)
    return u


@pytest.fixture()
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.start_run = AsyncMock()
    runner.resume_run = AsyncMock()
    runner.cancel_run = AsyncMock()

    async def fake_stream(run_id):
        yield {"event": "events/metadata", "data": {"run_id": run_id}}

    runner.get_event_stream = fake_stream
    return runner


@pytest.fixture()
def current_user() -> User:
    return _user()


@pytest.fixture()
def client(current_user: User, mock_runner: MagicMock) -> AsyncClient:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_current_user_or_system] = lambda: current_user
    app.dependency_overrides[get_current_user_sse] = lambda: current_user
    app.dependency_overrides[get_lg_runner] = lambda: mock_runner
    transport = ASGITransport(app=app)
    c = AsyncClient(transport=transport, base_url="http://test")
    yield c
    app.dependency_overrides.clear()


class TestAgentRouter:
    @patch("backend.api.routers.agent.agent_service")
    async def test_create_run(self, mock_svc, client) -> None:
        from backend.services.agent_service import RunResult

        tid = uuid.uuid4()
        mock_svc.trigger_run = AsyncMock(
            return_value=RunResult(
                run_id="r1",
                thread_id=str(tid),
                status="running",
                stream_url=f"/api/v1/agent/threads/{tid}/runs/r1/stream",
            ),
        )
        mock_svc.update_thread_status = AsyncMock()
        response = await client.post(
            f"/api/v1/agent/threads/{tid}/runs",
            json={"message": "hello"},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "running"

    @patch("backend.api.routers.agent.agent_service")
    async def test_create_run_not_found(self, mock_svc, client) -> None:
        mock_svc.trigger_run = AsyncMock(return_value=None)
        response = await client.post(
            f"/api/v1/agent/threads/{uuid.uuid4()}/runs",
            json={"message": "hello"},
        )
        assert response.status_code == 404

    @patch("backend.api.routers.agent.agent_service")
    async def test_cancel_run(self, mock_svc, client) -> None:
        mock_svc.cancel_run = AsyncMock(return_value=True)
        tid = uuid.uuid4()
        response = await client.post(f"/api/v1/agent/threads/{tid}/runs/r1/cancel")
        assert response.status_code == 204

    @patch("backend.api.routers.agent._verify_thread_ownership", new_callable=AsyncMock)
    async def test_stream_returns_sse(self, mock_verify, client) -> None:
        tid = uuid.uuid4()
        response = await client.get(f"/api/v1/agent/threads/{tid}/runs/r1/stream")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @patch("backend.api.routers.agent._verify_thread_ownership", new_callable=AsyncMock)
    async def test_stream_error_sends_error_and_run_end(
        self, mock_verify, client, mock_runner
    ) -> None:
        """Runner 抛异常时 SSE 应先发 error 事件再发 run_end。"""
        import json as _json

        async def failing_stream(run_id):
            raise RuntimeError("db connection lost")
            yield

        mock_runner.get_event_stream = failing_stream

        tid = uuid.uuid4()
        response = await client.get(f"/api/v1/agent/threads/{tid}/runs/r1/stream")
        assert response.status_code == 200

        lines = response.text.strip().split("\n")
        data_lines = [line for line in lines if line.startswith("data: ")]
        assert len(data_lines) >= 2

        error_evt = _json.loads(data_lines[-2].removeprefix("data: "))
        assert error_evt["event_type"] == "error"
        assert error_evt["data"]["error_type"] == "INTERNAL_ERROR"

        end_evt = _json.loads(data_lines[-1].removeprefix("data: "))
        assert end_evt["event_type"] == "run_end"


class TestAgentRouterHelpers:
    def test_normalize_pending_interrupt_wraps_payload(self) -> None:
        interrupt = agent_router._normalize_pending_interrupt(  # type: ignore[attr-defined]
            {
                "action": "confirm_execute",
                "run_id": "run-1",
                "thread_id": "th-1",
                "code": "print('hello')",
                "title": "Review code",
            }
        )

        assert interrupt == {
            "action": "confirm_execute",
            "run_id": "run-1",
            "thread_id": "th-1",
            "payload": {
                "code": "print('hello')",
                "title": "Review code",
            },
        }

    def test_determine_terminal_status_marks_failed_on_error(self) -> None:
        status = agent_router._determine_terminal_status(  # type: ignore[attr-defined]
            existing_status="running",
            was_interrupted=False,
            saw_error_event=True,
        )

        assert status == "failed"

    def test_determine_terminal_status_preserves_cancelled(self) -> None:
        status = agent_router._determine_terminal_status(  # type: ignore[attr-defined]
            existing_status="cancelled",
            was_interrupted=False,
            saw_error_event=False,
        )

        assert status == "cancelled"


class TestResumeRunAuthPropagation:
    """resume_run 端点应将 auth_token 传播到 LangGraphRunner config。"""

    @patch("backend.api.routers.agent._verify_thread_ownership", new_callable=AsyncMock)
    @patch("backend.api.routers.agent.agent_service")
    @patch("backend.api.routers.agent.base_repo")
    async def test_resume_run_propagates_auth_token(
        self, mock_base_repo, mock_svc, mock_verify, client, mock_runner
    ) -> None:
        mock_base_repo.create = AsyncMock()
        mock_svc.update_thread_status = AsyncMock()
        tid = uuid.uuid4()

        response = await client.post(
            f"/api/v1/agent/threads/{tid}/runs/r1/resume",
            json={"action": "approve", "payload": {"selected_ids": ["p1"]}},
            headers={"Authorization": "Bearer test-token-123"},
        )
        assert response.status_code == 200

        # runner.resume_run 应被调用且 config 包含 auth_token
        mock_runner.resume_run.assert_awaited_once()
        call_kwargs = mock_runner.resume_run.call_args.kwargs
        assert call_kwargs["config"] is not None
        assert call_kwargs["config"]["configurable"]["auth_token"] == "Bearer test-token-123"

    @patch("backend.api.routers.agent._verify_thread_ownership", new_callable=AsyncMock)
    @patch("backend.api.routers.agent.agent_service")
    @patch("backend.api.routers.agent.base_repo")
    async def test_resume_run_without_auth_passes_none_config(
        self, mock_base_repo, mock_svc, mock_verify, client, mock_runner
    ) -> None:
        """无 Authorization header 时 config 应为 None。"""
        mock_base_repo.create = AsyncMock()
        mock_svc.update_thread_status = AsyncMock()
        tid = uuid.uuid4()

        # client fixture 已有 dependency override 跳过 auth，
        # 但此处不发 Authorization header
        response = await client.post(
            f"/api/v1/agent/threads/{tid}/runs/r1/resume",
            json={"action": "approve"},
        )
        assert response.status_code == 200

        call_kwargs = mock_runner.resume_run.call_args.kwargs
        assert call_kwargs["config"] is None


class TestAgentThreadMessages:
    @patch("backend.api.routers.agent._verify_thread_ownership", new_callable=AsyncMock)
    @patch("backend.api.routers.agent.run_snapshot_repo")
    async def test_get_thread_messages_aggregates_content_blocks(
        self, mock_repo, mock_verify, client
    ) -> None:
        tid = uuid.uuid4()

        # mock 两个 snapshot
        snap1 = MagicMock()
        snap1.run_id = uuid.uuid4()
        snap1.user_message = "msg 1"
        snap1.assistant_response = "reply 1"
        snap1.created_at = datetime.now(tz=UTC)
        snap1.completed_at = snap1.created_at
        snap1.status = "completed"
        snap1.cot_nodes = None
        snap1.content_blocks = [{"content": "block1", "workflow": "discovery"}]

        snap2 = MagicMock()
        snap2.run_id = uuid.uuid4()
        snap2.user_message = "msg 2"
        snap2.assistant_response = None
        snap2.created_at = datetime.now(tz=UTC)
        snap2.completed_at = None
        snap2.status = "running"
        snap2.cot_nodes = [{"name": "node1", "status": "running"}]
        snap2.content_blocks = [{"content": "block2", "workflow": "extraction"}]

        # list_by_thread 会返回降序排列的，代码中通过 reverse() 处理
        mock_repo.list_by_thread = AsyncMock(return_value=[snap2, snap1])

        response = await client.get(f"/api/v1/agent/threads/{tid}/messages")
        assert response.status_code == 200

        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 3  # msg1, reply1, msg2

        # 验证 content_blocks 是否合并返回
        assert "content_blocks" in data
        assert data["content_blocks"] == [
            {"content": "block1", "workflow": "discovery"},
            {"content": "block2", "workflow": "extraction"},
        ]
