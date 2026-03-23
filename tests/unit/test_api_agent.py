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
