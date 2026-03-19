"""Editor draft API router."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.editor import DraftLoad, DraftSave
from backend.models.user import User
from backend.repositories import editor_repo

router = APIRouter(prefix="/api/v1/drafts", tags=["editor"])


@router.put("/{thread_id}", response_model=DraftLoad)
async def save_draft(
    thread_id: uuid.UUID,
    body: DraftSave,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftLoad:
    """Save or update editor draft for a thread."""
    # TODO(P2): verify thread ownership via workspace chain
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
    # TODO(P2): verify thread ownership via workspace chain
    draft = await editor_repo.get_by_thread_id(session, thread_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return DraftLoad.model_validate(draft)
