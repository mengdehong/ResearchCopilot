"""Editor API router tests."""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.models.editor_draft import EditorDraft
from backend.models.user import User


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


def _make_draft(thread_id: uuid.UUID) -> EditorDraft:
    draft = EditorDraft()
    draft.id = uuid.uuid4()
    draft.thread_id = thread_id
    draft.content = "# My Draft"
    draft.created_at = datetime.now(tz=UTC)
    draft.updated_at = datetime.now(tz=UTC)
    return draft


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


class TestEditorRouter:
    @patch("backend.api.routers.editor.editor_repo")
    async def test_save_draft(
        self, mock_repo: MagicMock,
        client: AsyncClient,
    ) -> None:
        thread_id = uuid.uuid4()
        draft = _make_draft(thread_id)
        mock_repo.upsert_draft = AsyncMock(return_value=draft)

        response = await client.put(
            f"/api/v1/drafts/{thread_id}",
            json={"content": "# My Draft"},
        )
        assert response.status_code == 200
        assert response.json()["content"] == "# My Draft"

    @patch("backend.api.routers.editor.editor_repo")
    async def test_load_draft(
        self, mock_repo: MagicMock,
        client: AsyncClient,
    ) -> None:
        thread_id = uuid.uuid4()
        draft = _make_draft(thread_id)
        mock_repo.get_by_thread_id = AsyncMock(return_value=draft)

        response = await client.get(f"/api/v1/drafts/{thread_id}")
        assert response.status_code == 200
        assert response.json()["thread_id"] == str(thread_id)

    @patch("backend.api.routers.editor.editor_repo")
    async def test_load_draft_not_found(
        self, mock_repo: MagicMock,
        client: AsyncClient,
    ) -> None:
        mock_repo.get_by_thread_id = AsyncMock(return_value=None)

        response = await client.get(f"/api/v1/drafts/{uuid.uuid4()}")
        assert response.status_code == 404
