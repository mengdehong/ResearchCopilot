"""Editor draft API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.editor import DraftLoad, DraftSave
from backend.models.user import User
from backend.services import editor_service

router = APIRouter(prefix="/api/editor/draft", tags=["editor"])


@router.put("", response_model=DraftLoad)
async def save_draft(
    thread_id: uuid.UUID,
    body: DraftSave,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftLoad:
    """Save or update editor draft for a thread."""
    draft = await editor_service.save_draft(
        session,
        thread_id,
        body.content,
        current_user,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Thread not found or access denied")
    await session.commit()
    await session.refresh(draft)
    return DraftLoad.model_validate(draft)


@router.get("/{thread_id}", response_model=DraftLoad)
async def load_draft(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftLoad:
    """Load editor draft for a thread. Returns empty content if no draft saved yet."""
    result = await editor_service.load_draft(session, thread_id, current_user)
    if result is None:
        raise HTTPException(status_code=404, detail="Thread not found or access denied")
    thread, draft = result
    if draft is None:
        return DraftLoad(
            thread_id=thread_id,
            content="",
            updated_at=thread.updated_at,
        )
    return DraftLoad.model_validate(draft)
