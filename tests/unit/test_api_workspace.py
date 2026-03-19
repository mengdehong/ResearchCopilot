"""Workspace API router tests — httpx AsyncClient + dependency overrides."""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.models.user import User
from backend.models.workspace import Workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    ws.discipline = "computer_science"
    ws.is_deleted = False
    ws.created_at = datetime.now(tz=UTC)
    ws.updated_at = datetime.now(tz=UTC)
    return ws


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user() -> User:
    return _make_user()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def client(mock_user: User, mock_session: AsyncMock) -> AsyncClient:
    """Create test client with mocked auth and DB dependencies."""
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

class TestWorkspaceRouter:
    @patch("backend.api.routers.workspace.workspace_repo")
    @patch("backend.api.routers.workspace.base_repo")
    async def test_create_workspace(
        self, mock_base: MagicMock, mock_ws_repo: MagicMock,
        client: AsyncClient, mock_user: User, mock_session: AsyncMock,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        mock_base.create = AsyncMock(return_value=ws)

        response = await client.post(
            "/api/v1/workspaces",
            json={"name": "My Research", "discipline": "physics"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test WS"

    @patch("backend.api.routers.workspace.workspace_repo")
    async def test_list_workspaces(
        self, mock_ws_repo: MagicMock,
        client: AsyncClient, mock_user: User,
    ) -> None:
        ws1 = _make_workspace(mock_user.id)
        ws2 = _make_workspace(mock_user.id)
        mock_ws_repo.list_by_owner = AsyncMock(return_value=[ws1, ws2])

        response = await client.get("/api/v1/workspaces")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @patch("backend.api.routers.workspace.base_repo")
    async def test_get_workspace_by_id(
        self, mock_base: MagicMock,
        client: AsyncClient, mock_user: User,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        mock_base.get_by_id = AsyncMock(return_value=ws)

        response = await client.get(f"/api/v1/workspaces/{ws.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(ws.id)

    @patch("backend.api.routers.workspace.base_repo")
    async def test_get_workspace_not_found(
        self, mock_base: MagicMock,
        client: AsyncClient,
    ) -> None:
        mock_base.get_by_id = AsyncMock(return_value=None)

        response = await client.get(f"/api/v1/workspaces/{uuid.uuid4()}")
        assert response.status_code == 404

    @patch("backend.api.routers.workspace.workspace_repo")
    @patch("backend.api.routers.workspace.base_repo")
    async def test_delete_workspace(
        self, mock_base: MagicMock, mock_ws_repo: MagicMock,
        client: AsyncClient, mock_user: User, mock_session: AsyncMock,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        mock_base.get_by_id = AsyncMock(return_value=ws)
        mock_ws_repo.soft_delete = AsyncMock()

        response = await client.delete(f"/api/v1/workspaces/{ws.id}")
        assert response.status_code == 204

    @patch("backend.api.routers.workspace.base_repo")
    async def test_delete_workspace_not_found(
        self, mock_base: MagicMock,
        client: AsyncClient,
    ) -> None:
        mock_base.get_by_id = AsyncMock(return_value=None)

        response = await client.delete(f"/api/v1/workspaces/{uuid.uuid4()}")
        assert response.status_code == 404

    @patch("backend.api.routers.workspace.base_repo")
    async def test_delete_workspace_forbidden(
        self, mock_base: MagicMock,
        client: AsyncClient, mock_user: User,
    ) -> None:
        ws = _make_workspace(uuid.uuid4())  # different owner
        mock_base.get_by_id = AsyncMock(return_value=ws)

        response = await client.delete(f"/api/v1/workspaces/{ws.id}")
        assert response.status_code == 403
