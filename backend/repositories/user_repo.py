"""User repository — pure functions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Get user by primary key."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_external_id(session: AsyncSession, external_id: str) -> User | None:
    """Get user by external auth provider ID."""
    stmt = select(User).where(User.external_id == external_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
