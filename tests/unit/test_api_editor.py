"""Editor router tests — mock editor_service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_current_user, get_db
from backend.main import app
from backend.models.editor_draft import EditorDraft
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


def _draft(thread_id: uuid.UUID) -> EditorDraft:
    d = EditorDraft()
    d.id = uuid.uuid4()
    d.thread_id = thread_id
    d.content = "draft content"
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


class TestEditorRouter:
    @patch("backend.api.routers.editor.editor_service")
    async def test_load_draft(self, mock_svc, client) -> None:
        tid = uuid.uuid4()
        
        class MockThread:
            updated_at = datetime.now(tz=UTC)
            
        mock_svc.load_draft = AsyncMock(return_value=(MockThread(), _draft(tid)))
        response = await client.get(f"/api/editor/draft/{tid}")
        assert response.status_code == 200
        assert response.json()["content"] == "draft content"

    @patch("backend.api.routers.editor.editor_service")
    async def test_load_draft_not_found(self, mock_svc, client) -> None:
        mock_svc.load_draft = AsyncMock(return_value=None)
        response = await client.get(f"/api/editor/draft/{uuid.uuid4()}")
        assert response.status_code == 404

    @patch("backend.api.routers.editor.editor_service")
    async def test_save_draft(self, mock_svc, client) -> None:
        tid = uuid.uuid4()
        mock_svc.save_draft = AsyncMock(return_value=_draft(tid))
        response = await client.put(
            f"/api/editor/draft?thread_id={tid}",
            json={"content": "new content"},
        )
        assert response.status_code == 200
