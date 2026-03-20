"""Agent router tests — mock agent_service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_current_user, get_db
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
def current_user() -> User:
    return _user()


@pytest.fixture()
def client(current_user: User) -> AsyncClient:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: current_user
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
                stream_url=f"/api/agent/threads/{tid}/runs/r1/stream",
            ),
        )
        response = await client.post(
            f"/api/agent/threads/{tid}/runs",
            json={"message": "hello"},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "running"

    @patch("backend.api.routers.agent.agent_service")
    async def test_create_run_not_found(self, mock_svc, client) -> None:
        mock_svc.trigger_run = AsyncMock(return_value=None)
        response = await client.post(
            f"/api/agent/threads/{uuid.uuid4()}/runs",
            json={"message": "hello"},
        )
        assert response.status_code == 404

    @patch("backend.api.routers.agent.agent_service")
    async def test_cancel_run(self, mock_svc, client) -> None:
        mock_svc.cancel_run = AsyncMock(return_value=True)
        tid = uuid.uuid4()
        response = await client.post(f"/api/agent/threads/{tid}/runs/r1/cancel")
        assert response.status_code == 204

    @patch("backend.api.routers.agent._verify_thread_ownership", new_callable=AsyncMock)
    @patch("backend.api.routers.agent.thread_repo")
    async def test_stream_returns_sse(self, mock_thread_repo, mock_verify, client) -> None:
        tid = uuid.uuid4()
        mock_thread = MagicMock()
        mock_thread.langgraph_thread_id = "lg-123"
        mock_thread_repo.get_by_id = AsyncMock(return_value=mock_thread)
        response = await client.get(f"/api/agent/threads/{tid}/runs/r1/stream")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
