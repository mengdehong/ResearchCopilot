"""Document router tests — mock document_service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_current_user, get_db
from backend.main import app
from backend.models.document import Document
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


def _doc(ws_id: uuid.UUID) -> Document:
    d = Document()
    d.id = uuid.uuid4()
    d.workspace_id = ws_id
    d.title = "Doc"
    d.file_path = "/test.pdf"
    d.parse_status = "pending"
    d.source = "upload"
    d.doi = None
    d.abstract_text = None
    d.year = None
    d.include_appendix = False
    d.created_at = d.updated_at = datetime.now(tz=UTC)
    return d


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


class TestDocumentRouter:
    @patch("backend.api.routers.document.document_service")
    async def test_list_documents(self, mock_svc, client, current_user) -> None:
        ws_id = uuid.uuid4()
        mock_svc.list_documents = AsyncMock(return_value=[_doc(ws_id)])
        response = await client.get(f"/api/v1/documents?workspace_id={ws_id}")
        assert response.status_code == 200
        assert len(response.json()) == 1

    @patch("backend.api.routers.document.document_service")
    async def test_get_document(self, mock_svc, client) -> None:
        doc = _doc(uuid.uuid4())
        mock_svc.get_document = AsyncMock(return_value=doc)
        response = await client.get(f"/api/v1/documents/{doc.id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Doc"

    @patch("backend.api.routers.document.document_service")
    async def test_get_document_not_found(self, mock_svc, client) -> None:
        mock_svc.get_document = AsyncMock(return_value=None)
        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}")
        assert response.status_code == 404

    @patch("backend.api.routers.document.document_service")
    async def test_get_document_status(self, mock_svc, client) -> None:
        doc = _doc(uuid.uuid4())
        mock_svc.get_document = AsyncMock(return_value=doc)
        response = await client.get(f"/api/v1/documents/{doc.id}/status")
        assert response.status_code == 200
        assert response.json()["parse_status"] == "pending"

    @patch("backend.api.routers.document.document_service")
    async def test_delete_document(self, mock_svc, client) -> None:
        mock_svc.delete_document = AsyncMock(return_value=True)
        response = await client.delete(f"/api/v1/documents/{uuid.uuid4()}")
        assert response.status_code == 204

    @patch("backend.api.routers.document.document_service")
    async def test_retry_parse(self, mock_svc, client) -> None:
        doc = _doc(uuid.uuid4())
        mock_svc.retry_parse = AsyncMock(return_value=doc)
        response = await client.post(f"/api/v1/documents/{doc.id}/retry")
        assert response.status_code == 200

    @patch("backend.api.routers.document.document_service")
    async def test_get_document_artifacts(self, mock_svc, client) -> None:
        doc_id = uuid.uuid4()
        mock_svc.get_document_artifacts = AsyncMock(
            return_value={
                "paragraphs": [{"content_text": "hello"}],
                "figures": [],
                "equations": [],
                "references": [],
            }
        )
        response = await client.get(f"/api/v1/documents/{doc_id}/artifacts")
        assert response.status_code == 200
        data = response.json()
        assert len(data["paragraphs"]) == 1

    @patch("backend.api.routers.document.document_service")
    async def test_get_document_artifacts_not_found(self, mock_svc, client) -> None:
        mock_svc.get_document_artifacts = AsyncMock(return_value=None)
        response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/artifacts")
        assert response.status_code == 404
