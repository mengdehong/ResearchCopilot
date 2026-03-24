"""Workspace router tests — mock workspace_service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_current_user, get_db
from backend.main import app
from backend.models.user import User
from backend.models.workspace import Workspace


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.external_id = "ext"
    u.email = "a@b.com"
    u.display_name = "Test"
    u.settings = {}
    u.created_at = u.updated_at = datetime.now(tz=UTC)
    return u


def _ws(owner_id: uuid.UUID) -> Workspace:
    ws = Workspace()
    ws.id = uuid.uuid4()
    ws.owner_id = owner_id
    ws.name = "WS"
    ws.discipline = "cs"
    ws.is_deleted = False
    ws.created_at = ws.updated_at = datetime.now(tz=UTC)
    return ws


@pytest.fixture()
def current_user() -> User:
    return _user()


@pytest.fixture()
def client(current_user: User) -> AsyncClient:
    session = AsyncMock()
    session.commit = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: current_user
    transport = ASGITransport(app=app)
    c = AsyncClient(transport=transport, base_url="http://test")
    yield c
    app.dependency_overrides.clear()


class TestWorkspaceRouter:
    @patch("backend.api.routers.workspace.workspace_service")
    async def test_create_workspace(self, mock_svc, client, current_user) -> None:
        ws = _ws(current_user.id)
        mock_svc.create_workspace = AsyncMock(return_value=ws)
        response = await client.post(
            "/api/v1/workspaces",
            json={"name": "WS", "discipline": "cs"},
        )
        assert response.status_code == 201

    @patch("backend.api.routers.workspace.workspace_service")
    async def test_list_workspaces(self, mock_svc, client, current_user) -> None:
        mock_svc.list_workspaces = AsyncMock(return_value=[_ws(current_user.id)])
        response = await client.get("/api/v1/workspaces")
        assert response.status_code == 200
        assert len(response.json()) == 1

    @patch("backend.api.routers.workspace.workspace_service")
    async def test_get_workspace_not_found(self, mock_svc, client) -> None:
        mock_svc.get_workspace = AsyncMock(return_value=None)
        response = await client.get(f"/api/v1/workspaces/{uuid.uuid4()}")
        assert response.status_code == 404

    @patch("backend.api.routers.workspace.workspace_service")
    async def test_delete_workspace(self, mock_svc, client) -> None:
        mock_svc.delete_workspace = AsyncMock(return_value=True)
        response = await client.delete(f"/api/v1/workspaces/{uuid.uuid4()}")
        assert response.status_code == 204

    @patch("backend.api.routers.workspace.workspace_service")
    async def test_get_summary(self, mock_svc, client, current_user) -> None:
        from backend.repositories.document_repo import DocStatusCounts
        from backend.services.workspace_service import WorkspaceSummary

        mock_svc.get_summary = AsyncMock(
            return_value=WorkspaceSummary(
                workspace_id=uuid.uuid4(),
                name="WS",
                document_count=3,
                thread_count=2,
                doc_status_counts=DocStatusCounts(completed=2, pending=1),
            ),
        )
        response = await client.get(f"/api/v1/workspaces/{uuid.uuid4()}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["document_count"] == 3
