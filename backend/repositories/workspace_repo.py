"""Workspace repository — pure functions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.workspace import Workspace
from backend.repositories.base import soft_delete as _base_soft_delete


async def list_by_owner(
    session: AsyncSession,
    owner_id: uuid.UUID,
) -> list[Workspace]:
    """List non-deleted workspaces owned by the given user."""
    stmt = select(Workspace).where(
        Workspace.owner_id == owner_id,
        Workspace.is_deleted.is_(False),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def soft_delete(session: AsyncSession, workspace: Workspace) -> None:
    """Soft-delete a workspace."""
    await _base_soft_delete(session, workspace)


async def update(
    session: AsyncSession,
    workspace: Workspace,
    *,
    name: str | None = None,
    discipline: str | None = None,
) -> Workspace:
    """Update workspace fields. Only provided values are changed."""
    if name is not None:
        workspace.name = name
    if discipline is not None:
        workspace.discipline = discipline
    await session.flush()
    return workspace
