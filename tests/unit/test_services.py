"""Service layer tests — mock repos/clients, verify business logic."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.exceptions import QuotaExceededError
from backend.models.document import Document
from backend.models.thread import Thread
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories.document_repo import DocStatusCounts


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


def _doc(ws_id: uuid.UUID) -> Document:
    d = Document()
    d.id = uuid.uuid4()
    d.workspace_id = ws_id
    d.title = "Doc"
    d.file_path = "/test.pdf"
    d.parse_status = "pending"
    d.source = "upload"
    d.include_appendix = False
    d.created_at = d.updated_at = datetime.now(tz=UTC)
    return d


def _thread(ws_id: uuid.UUID) -> Thread:
    t = Thread()
    t.id = uuid.uuid4()
    t.workspace_id = ws_id
    t.title = "Thread"
    t.status = "creating"
    t.langgraph_thread_id = "lg-123"
    t.created_at = t.updated_at = datetime.now(tz=UTC)
    return t


# ---------------------------------------------------------------------------
# workspace_service
# ---------------------------------------------------------------------------


class TestWorkspaceService:
    @patch("backend.services.workspace_service.base_repo")
    async def test_create_workspace(self, mock_base: MagicMock) -> None:
        from backend.services.workspace_service import create_workspace

        session = AsyncMock()
        owner = _user()
        mock_base.create = AsyncMock(side_effect=lambda s, ws: ws)

        result = await create_workspace(session, owner=owner, name="WS", discipline="cs")
        assert result.name == "WS"
        assert result.owner_id == owner.id

    @patch("backend.services.workspace_service.workspace_repo")
    @patch("backend.services.workspace_service.base_repo")
    async def test_get_workspace_forbidden(self, mock_base: MagicMock, _) -> None:
        from backend.services.workspace_service import get_workspace

        session = AsyncMock()
        owner = _user()
        ws = _ws(uuid.uuid4())  # different owner
        mock_base.get_by_id = AsyncMock(return_value=ws)

        result = await get_workspace(session, ws.id, owner)
        assert result is None

    @patch("backend.services.workspace_service.document_repo")
    @patch("backend.services.workspace_service.workspace_repo")
    @patch("backend.services.workspace_service.base_repo")
    async def test_get_summary(
        self,
        mock_base: MagicMock,
        mock_ws: MagicMock,
        mock_doc: MagicMock,
    ) -> None:
        from backend.services.workspace_service import get_summary

        session = AsyncMock()
        owner = _user()
        ws = _ws(owner.id)
        mock_base.get_by_id = AsyncMock(return_value=ws)
        mock_doc.list_by_workspace = AsyncMock(return_value=[_doc(ws.id)])
        mock_doc.count_by_status = AsyncMock(
            return_value=DocStatusCounts(pending=1),
        )

        result = await get_summary(session, ws.id, owner)
        assert result is not None
        assert result.document_count == 1


# ---------------------------------------------------------------------------
# document_service
# ---------------------------------------------------------------------------


class TestDocumentService:
    @patch("backend.services.document_service.document_repo")
    @patch("backend.services.document_service.base_repo")
    async def test_list_documents(
        self,
        mock_base: MagicMock,
        mock_doc: MagicMock,
    ) -> None:
        from backend.services.document_service import list_documents

        session = AsyncMock()
        owner = _user()
        ws = _ws(owner.id)
        mock_base.get_by_id = AsyncMock(return_value=ws)
        mock_doc.list_by_workspace = AsyncMock(return_value=[_doc(ws.id)])

        result = await list_documents(session, ws.id, owner)
        assert result is not None
        assert len(result) == 1


# ---------------------------------------------------------------------------
# agent_service
# ---------------------------------------------------------------------------


class TestAgentService:
    @patch("backend.services.agent_service.base_repo")
    async def test_trigger_run(self, mock_base: MagicMock) -> None:
        from backend.services.agent_service import trigger_run

        session = AsyncMock()
        owner = _user()
        ws = _ws(owner.id)
        thread = _thread(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws])
        mock_base.create = AsyncMock(side_effect=lambda s, obj: obj)

        runner = MagicMock()
        runner.start_run = AsyncMock()

        result = await trigger_run(
            session,
            runner,
            thread_id=thread.id,
            message="hello",
            owner=owner,
        )
        assert result is not None
        assert result.status == "running"
        runner.start_run.assert_awaited_once()

    @patch("backend.services.agent_service.base_repo")
    async def test_trigger_run_forbidden(self, mock_base: MagicMock) -> None:
        from backend.services.agent_service import trigger_run

        session = AsyncMock()
        owner = _user()
        thread = _thread(uuid.uuid4())  # workspace not owned
        ws = _ws(uuid.uuid4())
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws])

        runner = MagicMock()
        result = await trigger_run(
            session,
            runner,
            thread_id=thread.id,
            message="hi",
            owner=owner,
        )
        assert result is None


# ---------------------------------------------------------------------------
# quota_service
# ---------------------------------------------------------------------------


class TestQuotaService:
    async def test_check_and_consume_exceeds_quota(self) -> None:
        from backend.services.quota_service import check_and_consume

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 999_999
        session.execute.return_value = mock_result

        with pytest.raises(QuotaExceededError):
            await check_and_consume(
                session,
                workspace_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                input_tokens=3000,
                output_tokens=2000,
                model_name="gpt-4",
                monthly_limit=1_000_000,
            )
