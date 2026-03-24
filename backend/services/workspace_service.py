"""Workspace service — BFF business logic for workspace CRUD + aggregation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import document_repo, thread_repo, workspace_repo

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.user import User
    from backend.repositories.document_repo import DocStatusCounts


@dataclass(frozen=True)
class WorkspaceSummary:
    """Aggregated workspace summary."""

    workspace_id: uuid.UUID
    name: str
    document_count: int
    thread_count: int
    doc_status_counts: DocStatusCounts


async def create_workspace(
    session: AsyncSession,
    *,
    owner: User,
    name: str,
    discipline: str,
) -> Workspace:
    """Create a new workspace for the given user."""
    ws = Workspace()
    ws.owner_id = owner.id
    ws.name = name
    ws.discipline = discipline
    ws.is_deleted = False
    return await base_repo.create(session, ws)


async def list_workspaces(
    session: AsyncSession,
    owner: User,
) -> list[Workspace]:
    """List all non-deleted workspaces owned by the user."""
    return await workspace_repo.list_by_owner(session, owner.id)


async def get_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner: User,
) -> Workspace | None:
    """Get a workspace by ID, verifying ownership."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != owner.id:
        return None
    return ws


async def update_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner: User,
    *,
    name: str | None = None,
    discipline: str | None = None,
) -> Workspace | None:
    """Update workspace fields. Returns None if not found or forbidden."""
    ws = await get_workspace(session, workspace_id, owner)
    if ws is None:
        return None
    return await workspace_repo.update(session, ws, name=name, discipline=discipline)


async def delete_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner: User,
) -> bool:
    """Soft-delete a workspace. Returns False if not found or forbidden."""
    ws = await get_workspace(session, workspace_id, owner)
    if ws is None:
        return False
    await workspace_repo.soft_delete(session, ws)
    return True


async def get_summary(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner: User,
) -> WorkspaceSummary | None:
    """Get workspace summary with aggregated doc and thread stats."""
    ws = await get_workspace(session, workspace_id, owner)
    if ws is None:
        return None

    docs, counts, threads = await asyncio.gather(
        document_repo.list_by_workspace(session, workspace_id),
        document_repo.count_by_status(session, workspace_id),
        thread_repo.list_by_workspace(session, workspace_id),
    )

    return WorkspaceSummary(
        workspace_id=ws.id,
        name=ws.name,
        document_count=len(docs),
        thread_count=len(threads),
        doc_status_counts=counts,
    )
