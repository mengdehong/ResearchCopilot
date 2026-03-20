"""Editor service — BFF business logic for draft management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.thread import Thread
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import editor_repo

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.editor_draft import EditorDraft
    from backend.models.user import User


async def _verify_thread_ownership(
    session: AsyncSession,
    thread_id: uuid.UUID,
    owner: User,
) -> Thread | None:
    """Verify thread→workspace→owner chain. Returns None if denied."""
    thread = await base_repo.get_by_id(session, Thread, thread_id)
    if thread is None:
        return None

    ws = await base_repo.get_by_id(session, Workspace, thread.workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != owner.id:
        return None

    return thread


async def save_draft(
    session: AsyncSession,
    thread_id: uuid.UUID,
    content: str,
    owner: User,
) -> EditorDraft | None:
    """Save or update editor draft. Returns None if thread not owned."""
    thread = await _verify_thread_ownership(session, thread_id, owner)
    if thread is None:
        return None

    draft = await editor_repo.upsert_draft(session, thread_id, content)
    await session.flush()
    return draft


async def load_draft(
    session: AsyncSession,
    thread_id: uuid.UUID,
    owner: User,
) -> EditorDraft | None:
    """Load editor draft. Returns None if not found or not owned."""
    thread = await _verify_thread_ownership(session, thread_id, owner)
    if thread is None:
        return None

    return await editor_repo.get_by_thread_id(session, thread_id)
