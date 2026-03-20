"""Editor draft API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.editor import DraftLoad, DraftSave
from backend.models.thread import Thread
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import editor_repo

router = APIRouter(prefix="/api/editor/draft", tags=["editor"])


async def _verify_thread_ownership(
    session: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
) -> Thread:
    """Verify that current_user owns the workspace containing the thread.

    Chain: EditorDraft.thread_id -> Thread.workspace_id -> Workspace.owner_id
    """
    thread = await base_repo.get_by_id(session, Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    ws = await base_repo.get_by_id(session, Workspace, thread.workspace_id)
    if ws is None or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return thread


@router.put("/{thread_id}", response_model=DraftLoad)
async def save_draft(
    thread_id: uuid.UUID,
    body: DraftSave,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftLoad:
    """Save or update editor draft for a thread."""
    await _verify_thread_ownership(session, thread_id, current_user)
    draft = await editor_repo.upsert_draft(session, thread_id, body.content)
    await session.commit()
    return DraftLoad.model_validate(draft)


@router.get("/{thread_id}", response_model=DraftLoad)
async def load_draft(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftLoad:
    """Load editor draft for a thread."""
    await _verify_thread_ownership(session, thread_id, current_user)
    draft = await editor_repo.get_by_thread_id(session, thread_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return DraftLoad.model_validate(draft)
