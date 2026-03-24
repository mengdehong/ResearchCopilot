"""Notification repository — CRUD for notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from backend.models.notification import Notification

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    event_type: str,
    title: str,
    body: str = "",
) -> Notification:
    """Create a new notification."""
    notif = Notification(
        user_id=user_id,
        workspace_id=workspace_id,
        event_type=event_type,
        title=title,
        body=body,
    )
    session.add(notif)
    await session.flush()
    return notif


async def list_by_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    """List notifications for a user, newest first."""
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_read(
    session: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Mark a single notification as read. Returns True if updated."""
    stmt = (
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def mark_all_read(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Mark all notifications as read. Returns count updated."""
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    result = await session.execute(stmt)
    return result.rowcount
