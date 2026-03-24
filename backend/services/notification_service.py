"""Notification service — business logic for in-app notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.repositories import notification_repo

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.notification import Notification


async def create_notification(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    event_type: str,
    title: str,
    body: str = "",
) -> Notification:
    """Create and persist a notification."""
    return await notification_repo.create(
        session,
        user_id=user_id,
        workspace_id=workspace_id,
        event_type=event_type,
        title=title,
        body=body,
    )


async def list_notifications(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    """List notifications for a user."""
    return await notification_repo.list_by_user(
        session, user_id, unread_only=unread_only, limit=limit, offset=offset
    )


async def mark_read(
    session: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Mark a single notification as read."""
    return await notification_repo.mark_read(session, notification_id, user_id)


async def mark_all_read(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Mark all notifications as read for a user."""
    return await notification_repo.mark_all_read(session, user_id)
