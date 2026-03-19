"""Repository 层单元测试 -- mock AsyncSession 验证 CRUD 调用。"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from backend.models.document import Document
from backend.models.editor_draft import EditorDraft
from backend.models.workspace import Workspace
from backend.repositories.base import create, get_by_id, list_all, soft_delete
from backend.repositories.document_repo import (
    list_by_workspace as doc_list_by_workspace,
)
from backend.repositories.document_repo import (
    update_parse_status,
)
from backend.repositories.editor_repo import get_by_thread_id, upsert_draft
from backend.repositories.workspace_repo import (
    list_by_owner,
)
from backend.repositories.workspace_repo import (
    soft_delete as ws_soft_delete,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_document(workspace_id: uuid.UUID) -> Document:
    doc = Document()
    doc.id = uuid.uuid4()
    doc.workspace_id = workspace_id
    doc.title = "Test Doc"
    doc.file_path = "/uploads/test.pdf"
    doc.parse_status = "pending"
    doc.source = "upload"
    doc.include_appendix = False
    doc.created_at = datetime.now(tz=UTC)
    doc.updated_at = datetime.now(tz=UTC)
    return doc


# ---------------------------------------------------------------------------
# base.py generic CRUD
# ---------------------------------------------------------------------------

class TestBaseCRUD:
    async def test_create_adds_and_flushes(self) -> None:
        session = AsyncMock()
        ws = _make_workspace(uuid.uuid4())

        result = await create(session, ws)

        session.add.assert_called_once_with(ws)
        session.flush.assert_awaited_once()
        assert result is ws

    async def test_get_by_id_returns_model(self) -> None:
        session = AsyncMock()
        ws = _make_workspace(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ws
        session.execute.return_value = mock_result

        result = await get_by_id(session, Workspace, ws.id)
        assert result is ws
        session.execute.assert_awaited_once()

    async def test_get_by_id_returns_none(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await get_by_id(session, Workspace, uuid.uuid4())
        assert result is None

    async def test_list_all_returns_scalars(self) -> None:
        session = AsyncMock()
        ws1 = _make_workspace(uuid.uuid4())
        ws2 = _make_workspace(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ws1, ws2]
        session.execute.return_value = mock_result

        results = await list_all(session, Workspace)
        assert len(results) == 2

    async def test_soft_delete_sets_flag(self) -> None:
        session = AsyncMock()
        ws = _make_workspace(uuid.uuid4())
        assert ws.is_deleted is False

        await soft_delete(session, ws)

        assert ws.is_deleted is True
        session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# workspace_repo
# ---------------------------------------------------------------------------

class TestWorkspaceRepo:
    async def test_list_by_owner(self) -> None:
        session = AsyncMock()
        owner_id = uuid.uuid4()
        ws = _make_workspace(owner_id)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ws]
        session.execute.return_value = mock_result

        results = await list_by_owner(session, owner_id)
        assert len(results) == 1
        session.execute.assert_awaited_once()

    async def test_soft_delete_workspace(self) -> None:
        session = AsyncMock()
        ws = _make_workspace(uuid.uuid4())
        assert ws.is_deleted is False

        await ws_soft_delete(session, ws)
        assert ws.is_deleted is True


# ---------------------------------------------------------------------------
# document_repo
# ---------------------------------------------------------------------------

class TestDocumentRepo:
    async def test_list_by_workspace(self) -> None:
        session = AsyncMock()
        workspace_id = uuid.uuid4()
        doc = _make_document(workspace_id)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [doc]
        session.execute.return_value = mock_result

        results = await doc_list_by_workspace(session, workspace_id)
        assert len(results) == 1

    async def test_update_parse_status(self) -> None:
        session = AsyncMock()
        doc = _make_document(uuid.uuid4())
        assert doc.parse_status == "pending"

        await update_parse_status(session, doc, "completed")
        assert doc.parse_status == "completed"
        session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# editor_repo
# ---------------------------------------------------------------------------

class TestEditorRepo:
    async def test_get_by_thread_id_returns_draft(self) -> None:
        session = AsyncMock()
        thread_id = uuid.uuid4()
        draft = EditorDraft()
        draft.id = uuid.uuid4()
        draft.thread_id = thread_id
        draft.content = "draft content"
        draft.created_at = datetime.now(tz=UTC)
        draft.updated_at = datetime.now(tz=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = draft
        session.execute.return_value = mock_result

        result = await get_by_thread_id(session, thread_id)
        assert result is draft

    async def test_get_by_thread_id_returns_none(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await get_by_thread_id(session, uuid.uuid4())
        assert result is None

    async def test_upsert_creates_new_draft(self) -> None:
        session = AsyncMock()
        thread_id = uuid.uuid4()

        # No existing draft
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await upsert_draft(session, thread_id, "new content")
        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert result.content == "new content"

    async def test_upsert_updates_existing_draft(self) -> None:
        session = AsyncMock()
        thread_id = uuid.uuid4()
        draft = EditorDraft()
        draft.id = uuid.uuid4()
        draft.thread_id = thread_id
        draft.content = "old content"
        draft.created_at = datetime.now(tz=UTC)
        draft.updated_at = datetime.now(tz=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = draft
        session.execute.return_value = mock_result

        result = await upsert_draft(session, thread_id, "updated content")
        assert result.content == "updated content"
        session.flush.assert_awaited_once()
