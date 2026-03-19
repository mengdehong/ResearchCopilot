"""Generic CRUD pure functions for repository layer.

All functions accept AsyncSession as first argument (no class state).
Use TypeVar for type-safe generic operations across ORM models.
"""

import uuid
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import Base

T = TypeVar("T", bound=Base)


async def create(session: AsyncSession, instance: T) -> T:
    """Add instance to session and flush."""
    session.add(instance)
    await session.flush()
    return instance


async def get_by_id(
    session: AsyncSession,
    model: type[T],
    entity_id: uuid.UUID,
) -> T | None:
    """Get a single entity by primary key."""
    stmt = select(model).where(model.id == entity_id)  # type: ignore[attr-defined]
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession, model: type[T]) -> list[T]:
    """List all entities of the given model type."""
    stmt = select(model)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def soft_delete(session: AsyncSession, instance: T) -> None:
    """Set is_deleted flag and flush.

    Assumes the model has an `is_deleted` boolean column.
    """
    instance.is_deleted = True  # type: ignore[attr-defined]
    await session.flush()
