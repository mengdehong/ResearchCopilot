"""Document API router tests."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.models.document import Document
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


def _make_document(workspace_id: uuid.UUID) -> Document:
    doc = Document()
    doc.id = uuid.uuid4()
    doc.workspace_id = workspace_id
    doc.title = "Test Paper"
    doc.file_path = "/uploads/test.pdf"
    doc.parse_status = "pending"
    doc.source = "upload"
    doc.doi = None
    doc.abstract_text = None
    doc.year = None
    doc.include_appendix = False
    doc.created_at = datetime.now(tz=UTC)
    doc.updated_at = datetime.now(tz=UTC)
    return doc


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


class TestDocumentRouter:
    @patch("backend.api.routers.document.base_repo")
    async def test_create_document(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        doc = _make_document(ws.id)

        # First call: get workspace, second call: create doc
        mock_base.get_by_id = AsyncMock(return_value=ws)
        mock_base.create = AsyncMock(return_value=doc)

        response = await client.post(
            "/api/v1/documents",
            json={
                "title": "Test Paper",
                "file_path": "/uploads/test.pdf",
                "workspace_id": str(ws.id),
            },
        )
        assert response.status_code == 201
        assert response.json()["title"] == "Test Paper"

    @patch("backend.api.routers.document.base_repo")
    async def test_create_document_workspace_not_found(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
    ) -> None:
        mock_base.get_by_id = AsyncMock(return_value=None)

        response = await client.post(
            "/api/v1/documents",
            json={
                "title": "Test",
                "file_path": "/test.pdf",
                "workspace_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 404

    @patch("backend.api.routers.document.base_repo")
    async def test_get_document(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        doc = _make_document(ws.id)

        # Two get_by_id calls: first for doc, second for workspace
        mock_base.get_by_id = AsyncMock(side_effect=[doc, ws])

        response = await client.get(f"/api/v1/documents/{doc.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(doc.id)

    @patch("backend.api.routers.document.base_repo")
    async def test_get_document_not_found(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
    ) -> None:
        mock_base.get_by_id = AsyncMock(return_value=None)

        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}")
        assert response.status_code == 404

    @patch("backend.api.routers.document.base_repo")
    async def test_get_document_status(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(mock_user.id)
        doc = _make_document(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[doc, ws])

        response = await client.get(f"/api/v1/documents/{doc.id}/status")
        assert response.status_code == 200
        assert response.json()["parse_status"] == "pending"

    @patch("backend.api.routers.document.base_repo")
    async def test_get_document_status_wrong_owner_returns_403(
        self,
        mock_base: MagicMock,
        client: AsyncClient,
        mock_user: User,
    ) -> None:
        ws = _make_workspace(uuid.uuid4())  # different owner
        doc = _make_document(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[doc, ws])

        response = await client.get(f"/api/v1/documents/{doc.id}/status")
        assert response.status_code == 403
