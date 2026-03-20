"""Workspace API router — CRUD + summary."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.workspace import WorkspaceCreate, WorkspaceDetail
from backend.models.user import User
from backend.services import workspace_service

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceDetail, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceDetail:
    """Create a new workspace."""
    ws = await workspace_service.create_workspace(
        session,
        owner=current_user,
        name=body.name,
        discipline=body.discipline,
    )
    await session.commit()
    return WorkspaceDetail.model_validate(ws)


@router.get("", response_model=list[WorkspaceDetail])
async def list_workspaces(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkspaceDetail]:
    """List all workspaces owned by the current user."""
    items = await workspace_service.list_workspaces(session, current_user)
    return [WorkspaceDetail.model_validate(ws) for ws in items]


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceDetail:
    """Get workspace by ID."""
    ws = await workspace_service.get_workspace(session, workspace_id, current_user)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceDetail.model_validate(ws)


@router.put("/{workspace_id}", response_model=WorkspaceDetail)
async def update_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceDetail:
    """Update workspace name/discipline."""
    ws = await workspace_service.update_workspace(
        session,
        workspace_id,
        current_user,
        name=body.name,
        discipline=body.discipline,
    )
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await session.commit()
    return WorkspaceDetail.model_validate(ws)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete a workspace."""
    ok = await workspace_service.delete_workspace(session, workspace_id, current_user)
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await session.commit()


@router.get("/{workspace_id}/summary")
async def get_workspace_summary(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get workspace summary with aggregated document stats."""
    summary = await workspace_service.get_summary(session, workspace_id, current_user)
    if summary is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "workspace_id": str(summary.workspace_id),
        "name": summary.name,
        "document_count": summary.document_count,
        "doc_status_counts": {
            "uploading": summary.doc_status_counts.uploading,
            "pending": summary.doc_status_counts.pending,
            "parsing": summary.doc_status_counts.parsing,
            "completed": summary.doc_status_counts.completed,
            "failed": summary.doc_status_counts.failed,
        },
    }
