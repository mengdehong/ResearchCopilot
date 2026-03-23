"""Run snapshot repository — pure functions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.run_snapshot import RunSnapshot


async def get_by_run_id(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> RunSnapshot | None:
    """Get snapshot by run_id."""
    stmt = select(RunSnapshot).where(RunSnapshot.run_id == run_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_by_thread(
    session: AsyncSession,
    thread_id: uuid.UUID,
) -> list[RunSnapshot]:
    """List all snapshots for a thread, ordered by creation time."""
    stmt = (
        select(RunSnapshot)
        .where(RunSnapshot.thread_id == thread_id)
        .order_by(RunSnapshot.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_by_thread(
    session: AsyncSession,
    thread_id: uuid.UUID,
) -> RunSnapshot | None:
    """Get most recent running snapshot for a thread."""
    stmt = (
        select(RunSnapshot)
        .where(
            RunSnapshot.thread_id == thread_id,
            RunSnapshot.status == "running",
        )
        .order_by(RunSnapshot.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
