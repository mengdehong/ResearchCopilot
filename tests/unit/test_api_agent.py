"""Agent API router tests — endpoint signatures, ownership, and 501 responses."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.models.thread import Thread
from backend.models.user import User
from backend.models.workspace import Workspace


def _make_user() -> User:
    user = User()
    user.id = uuid.uuid4()
    user.external_id = "ext-123"
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.settings = {}
    user.created_at = datetime.now(tz=UTC)
    user.updated_at = datetime.now(tz=UTC)
    return user


def _make_workspace(owner_id: uuid.UUID) -> Workspace:
    ws = Workspace()
    ws.id = uuid.uuid4()
    ws.owner_id = owner_id
    ws.name = "Test WS"
    ws.discipline = "cs"
    ws.is_deleted = False
    ws.created_at = datetime.now(tz=UTC)
    ws.updated_at = datetime.now(tz=UTC)
    return ws


def _make_thread(workspace_id: uuid.UUID) -> Thread:
    thread = Thread()
    thread.id = uuid.uuid4()
    thread.workspace_id = workspace_id
    thread.title = "Test Thread"
    thread.status = "creating"
    thread.langgraph_thread_id = None
    thread.created_at = datetime.now(tz=UTC)
    thread.updated_at = datetime.now(tz=UTC)
    return thread


@pytest.fixture
def mock_user() -> User:
    return _make_user()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def client(mock_user: User, mock_session: AsyncMock) -> AsyncClient:
    from backend.api.dependencies import get_current_user, get_db
    from backend.main import app

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentRouter:
    @patch("backend.api.routers.agent.base_repo")
    async def test_create_run_returns_501(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        thread = _make_thread(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws])

        response = await client.post(
            f"/api/agent/threads/{thread.id}/runs",
            json={"message": "summarize this paper"},
        )
        assert response.status_code == 501
        assert "not yet implemented" in response.json()["detail"]

    @patch("backend.api.routers.agent.base_repo")
    async def test_stream_events_returns_501(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        thread = _make_thread(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws])

        response = await client.get(f"/api/agent/threads/{thread.id}/events")
        assert response.status_code == 501

    @patch("backend.api.routers.agent.base_repo")
    async def test_interrupt_returns_501(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        thread = _make_thread(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws])

        response = await client.post(
            f"/api/agent/threads/{thread.id}/interrupt",
            json={"action": "approve"},
        )
        assert response.status_code == 501

    @patch("backend.api.routers.agent.base_repo")
    async def test_create_run_thread_not_found(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
    ) -> None:
        mock_base.get_by_id = AsyncMock(return_value=None)

        response = await client.post(
            f"/api/agent/threads/{uuid.uuid4()}/runs",
            json={"message": "test"},
        )
        assert response.status_code == 404

    @patch("backend.api.routers.agent.base_repo")
    async def test_create_run_wrong_owner(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(uuid.uuid4())  # different owner
        thread = _make_thread(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws])

        response = await client.post(
            f"/api/agent/threads/{thread.id}/runs",
            json={"message": "test"},
        )
        assert response.status_code == 403
