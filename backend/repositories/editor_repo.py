"""Editor draft repository — pure functions."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.editor_draft import EditorDraft


async def get_by_thread_id(
    session: AsyncSession, thread_id: uuid.UUID,
) -> EditorDraft | None:
    """Get draft by thread_id (unique constraint)."""
    stmt = select(EditorDraft).where(EditorDraft.thread_id == thread_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_draft(
    session: AsyncSession, thread_id: uuid.UUID, content: str,
) -> EditorDraft:
    """Create or update draft for a thread."""
    existing = await get_by_thread_id(session, thread_id)
    if existing is not None:
        existing.content = content
        await session.flush()
        return existing

    draft = EditorDraft()
    draft.thread_id = thread_id
    draft.content = content
    session.add(draft)
    await session.flush()
    return draft
