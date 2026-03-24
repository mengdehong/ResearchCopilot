"""Thread repository — pure functions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.thread import Thread


async def get_by_id(session: AsyncSession, thread_id: uuid.UUID) -> Thread | None:
    """Get thread by primary key."""
    stmt = select(Thread).where(Thread.id == thread_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_by_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int | None = None,
) -> list[Thread]:
    """List all threads in a workspace, sorted by updated_at descending."""
    stmt = (
        select(Thread).where(Thread.workspace_id == workspace_id).order_by(Thread.updated_at.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
