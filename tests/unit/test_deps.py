"""依赖注入单元测试 — get_session / get_current_user / get_workspace。"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import HTTPException

from backend.api.dependencies import get_current_user, get_session, get_workspace
from backend.core.config import Settings
from backend.models.user import User
from backend.models.workspace import Workspace

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
        jwt_secret="test-secret",
        jwt_algorithm="HS256",
    )


@pytest.fixture
def sample_user() -> User:
    user = User()
    user.id = uuid.uuid4()
    user.external_id = "ext-123"
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.settings = {}
    user.created_at = datetime.now(tz=UTC)
    user.updated_at = datetime.now(tz=UTC)
    return user


@pytest.fixture
def valid_token(settings: Settings, sample_user: User) -> str:
    payload = {
        "sub": str(sample_user.id),
        "exp": datetime.now(tz=UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def expired_token(settings: Settings, sample_user: User) -> str:
    payload = {
        "sub": str(sample_user.id),
        "exp": datetime.now(tz=UTC) - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------

class TestGetSession:
    async def test_yields_session_and_closes(self) -> None:
        mock_session = AsyncMock()

        # async_sessionmaker() returns an async context manager
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False

        mock_factory = MagicMock()
        mock_factory.return_value = mock_ctx

        sessions: list[AsyncMock] = []
        async for session in get_session(mock_factory):
            sessions.append(session)

        assert len(sessions) == 1
        assert sessions[0] is mock_session


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    async def test_valid_token_returns_user(
        self, settings: Settings, sample_user: User, valid_token: str,
    ) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_session.execute.return_value = mock_result

        user = await get_current_user(
            token=valid_token, session=mock_session, settings=settings,
        )
        assert user.id == sample_user.id

    async def test_missing_token_raises_401(self, settings: Settings) -> None:
        mock_session = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=None, session=mock_session, settings=settings)
        assert exc_info.value.status_code == 401

    async def test_expired_token_raises_401(
        self, settings: Settings, expired_token: str,
    ) -> None:
        mock_session = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=expired_token, session=mock_session, settings=settings,
            )
        assert exc_info.value.status_code == 401

    async def test_user_not_found_raises_401(
        self, settings: Settings, valid_token: str,
    ) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=valid_token, session=mock_session, settings=settings,
            )
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_workspace
# ---------------------------------------------------------------------------

class TestGetWorkspace:
    async def test_valid_workspace_returns_it(self, sample_user: User) -> None:
        workspace = Workspace()
        workspace.id = uuid.uuid4()
        workspace.owner_id = sample_user.id
        workspace.name = "Test WS"
        workspace.discipline = "computer_science"
        workspace.is_deleted = False
        workspace.created_at = datetime.now(tz=UTC)
        workspace.updated_at = datetime.now(tz=UTC)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = workspace
        mock_session.execute.return_value = mock_result

        result = await get_workspace(
            workspace_id=workspace.id,
            session=mock_session,
            current_user=sample_user,
        )
        assert result.id == workspace.id

    async def test_workspace_not_found_raises_404(self, sample_user: User) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace(
                workspace_id=uuid.uuid4(),
                session=mock_session,
                current_user=sample_user,
            )
        assert exc_info.value.status_code == 404

    async def test_wrong_owner_raises_403(self, sample_user: User) -> None:
        workspace = Workspace()
        workspace.id = uuid.uuid4()
        workspace.owner_id = uuid.uuid4()  # different owner
        workspace.name = "Other WS"
        workspace.discipline = "computer_science"
        workspace.is_deleted = False
        workspace.created_at = datetime.now(tz=UTC)
        workspace.updated_at = datetime.now(tz=UTC)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = workspace
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace(
                workspace_id=workspace.id,
                session=mock_session,
                current_user=sample_user,
            )
        assert exc_info.value.status_code == 403

    async def test_deleted_workspace_raises_404(self, sample_user: User) -> None:
        workspace = Workspace()
        workspace.id = uuid.uuid4()
        workspace.owner_id = sample_user.id
        workspace.name = "Deleted WS"
        workspace.discipline = "computer_science"
        workspace.is_deleted = True
        workspace.created_at = datetime.now(tz=UTC)
        workspace.updated_at = datetime.now(tz=UTC)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = workspace
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace(
                workspace_id=workspace.id,
                session=mock_session,
                current_user=sample_user,
            )
        assert exc_info.value.status_code == 404
