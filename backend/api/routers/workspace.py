"""Workspace CRUD API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.workspace import WorkspaceCreate, WorkspaceDetail, WorkspaceList
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import workspace_repo

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", status_code=201, response_model=WorkspaceDetail)
async def create_workspace(
    body: WorkspaceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceDetail:
    """Create a new workspace."""
    ws = Workspace()
    ws.name = body.name
    ws.discipline = body.discipline
    ws.owner_id = current_user.id
    ws.is_deleted = False

    created = await base_repo.create(session, ws)
    await session.commit()
    return WorkspaceDetail.model_validate(created)


@router.get("", response_model=WorkspaceList)
async def list_workspaces(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceList:
    """List workspaces owned by the current user."""
    items = await workspace_repo.list_by_owner(session, current_user.id)
    details = [WorkspaceDetail.model_validate(ws) for ws in items]
    return WorkspaceList(items=details, total=len(details))


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace_detail(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceDetail:
    """Get workspace by ID."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return WorkspaceDetail.model_validate(ws)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Soft-delete a workspace."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await workspace_repo.soft_delete(session, ws)
    await session.commit()
    return Response(status_code=204)
