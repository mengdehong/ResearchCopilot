"""Notification service — TDD tests."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.notification import Notification


class TestNotificationService:
    """Test notification CRUD via the service layer."""

    @patch("backend.services.notification_service.notification_repo")
    async def test_create_notification(self, mock_repo: MagicMock) -> None:
        from backend.services.notification_service import create_notification

        session = AsyncMock()
        user_id = uuid.uuid4()
        ws_id = uuid.uuid4()

        expected = Notification(
            user_id=user_id,
            workspace_id=ws_id,
            event_type="task_completed",
            title="Document parsed",
            body="Your document has been parsed.",
        )
        mock_repo.create = AsyncMock(return_value=expected)

        result = await create_notification(
            session,
            user_id=user_id,
            workspace_id=ws_id,
            event_type="task_completed",
            title="Document parsed",
            body="Your document has been parsed.",
        )

        assert result.event_type == "task_completed"
        assert result.title == "Document parsed"
        mock_repo.create.assert_awaited_once()

    @patch("backend.services.notification_service.notification_repo")
    async def test_list_notifications(self, mock_repo: MagicMock) -> None:
        from backend.services.notification_service import list_notifications

        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_repo.list_by_user = AsyncMock(return_value=[])

        result = await list_notifications(session, user_id, unread_only=True)
        assert result == []
        mock_repo.list_by_user.assert_awaited_once_with(
            session, user_id, unread_only=True, limit=50, offset=0
        )

    @patch("backend.services.notification_service.notification_repo")
    async def test_mark_read(self, mock_repo: MagicMock) -> None:
        from backend.services.notification_service import mark_read

        session = AsyncMock()
        user_id = uuid.uuid4()
        notif_id = uuid.uuid4()

        mock_repo.mark_read = AsyncMock(return_value=True)

        result = await mark_read(session, notif_id, user_id)
        assert result is True

    @patch("backend.services.notification_service.notification_repo")
    async def test_mark_all_read(self, mock_repo: MagicMock) -> None:
        from backend.services.notification_service import mark_all_read

        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_repo.mark_all_read = AsyncMock(return_value=5)

        result = await mark_all_read(session, user_id)
        assert result == 5
