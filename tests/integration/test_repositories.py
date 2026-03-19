"""Repository integration tests — real AsyncSession against PostgreSQL.

These tests require a running PostgreSQL instance.
Set DATABASE_URL env var or skip with: pytest -m "not integration"
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.base import Base
from backend.models.document import Document
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import document_repo, editor_repo, workspace_repo

# Mark entire module as integration
pytestmark = pytest.mark.integration

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/research_copilot_test"


@pytest.fixture(scope="module")
async def engine():
    """Create test database engine and tables."""
    eng = create_async_engine(DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session(engine) -> AsyncSession:
    """Provide a transactional session that rolls back after each test."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess, sess.begin():
        yield sess
        await sess.rollback()


# ---------------------------------------------------------------------------
# base + workspace repo
# ---------------------------------------------------------------------------


class TestWorkspaceIntegration:
    async def test_create_and_get_workspace(self, session: AsyncSession) -> None:
        ws = Workspace()
        ws.owner_id = uuid.uuid4()
        ws.name = "Integration Test WS"
        ws.discipline = "physics"
        ws.is_deleted = False

        created = await base_repo.create(session, ws)
        assert created.id is not None

        fetched = await base_repo.get_by_id(session, Workspace, created.id)
        assert fetched is not None
        assert fetched.name == "Integration Test WS"

    async def test_list_by_owner(self, session: AsyncSession) -> None:
        owner_id = uuid.uuid4()

        for i in range(3):
            ws = Workspace()
            ws.owner_id = owner_id
            ws.name = f"WS {i}"
            ws.discipline = "cs"
            ws.is_deleted = False
            await base_repo.create(session, ws)

        results = await workspace_repo.list_by_owner(session, owner_id)
        assert len(results) == 3

    async def test_soft_delete_excludes_from_list(self, session: AsyncSession) -> None:
        owner_id = uuid.uuid4()

        ws = Workspace()
        ws.owner_id = owner_id
        ws.name = "To Delete"
        ws.discipline = "cs"
        ws.is_deleted = False
        await base_repo.create(session, ws)

        await workspace_repo.soft_delete(session, ws)
        results = await workspace_repo.list_by_owner(session, owner_id)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# document repo
# ---------------------------------------------------------------------------


class TestDocumentIntegration:
    async def test_create_and_list_by_workspace(self, session: AsyncSession) -> None:
        ws = Workspace()
        ws.owner_id = uuid.uuid4()
        ws.name = "Doc Test WS"
        ws.discipline = "cs"
        ws.is_deleted = False
        await base_repo.create(session, ws)

        doc = Document()
        doc.workspace_id = ws.id
        doc.title = "Integration Paper"
        doc.file_path = "/uploads/integration.pdf"
        doc.parse_status = "pending"
        doc.source = "upload"
        doc.include_appendix = False
        await base_repo.create(session, doc)

        docs = await document_repo.list_by_workspace(session, ws.id)
        assert len(docs) == 1
        assert docs[0].title == "Integration Paper"

    async def test_update_parse_status(self, session: AsyncSession) -> None:
        ws = Workspace()
        ws.owner_id = uuid.uuid4()
        ws.name = "Parse WS"
        ws.discipline = "cs"
        ws.is_deleted = False
        await base_repo.create(session, ws)

        doc = Document()
        doc.workspace_id = ws.id
        doc.title = "Status Test"
        doc.file_path = "/test.pdf"
        doc.parse_status = "pending"
        doc.source = "upload"
        doc.include_appendix = False
        await base_repo.create(session, doc)

        await document_repo.update_parse_status(session, doc, "completed")
        assert doc.parse_status == "completed"


# ---------------------------------------------------------------------------
# editor repo
# ---------------------------------------------------------------------------


class TestEditorDraftIntegration:
    async def test_upsert_creates_and_updates(self, session: AsyncSession) -> None:
        thread_id = uuid.uuid4()

        # Create
        draft = await editor_repo.upsert_draft(session, thread_id, "v1 content")
        assert draft.content == "v1 content"
        assert draft.thread_id == thread_id

        # Update
        updated = await editor_repo.upsert_draft(session, thread_id, "v2 content")
        assert updated.content == "v2 content"
        assert updated.id == draft.id  # same row

    async def test_get_by_thread_returns_none(self, session: AsyncSession) -> None:
        result = await editor_repo.get_by_thread_id(session, uuid.uuid4())
        assert result is None
