"""Quota guard dependency — TDD tests.

Tests that create_run is blocked when workspace quota is exhausted.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from backend.core.exceptions import QuotaExceededError
from backend.services.quota_service import QuotaStatus

# ---------------------------------------------------------------------------
# quota_guard pure function
# ---------------------------------------------------------------------------


class TestQuotaGuard:
    """Test the quota_guard dependency that pre-checks quota before runs."""

    async def test_allows_run_when_quota_remaining(self) -> None:
        """quota_guard should not raise when quota has remaining tokens."""
        from backend.api.dependencies import quota_guard

        session = AsyncMock()
        workspace_id = uuid.uuid4()

        with patch(
            "backend.services.quota_service.get_quota_status",
            new_callable=AsyncMock,
        ) as mock_qs:
            mock_qs.return_value = QuotaStatus(
                used_tokens=100_000,
                limit_tokens=1_000_000,
                remaining_tokens=900_000,
            )
            # Should not raise
            await quota_guard(session=session, workspace_id=workspace_id)
            mock_qs.assert_awaited_once_with(session, workspace_id)

    async def test_raises_when_quota_exhausted(self) -> None:
        """quota_guard should raise QuotaExceededError when no tokens remain."""
        from backend.api.dependencies import quota_guard

        session = AsyncMock()
        workspace_id = uuid.uuid4()

        with patch(
            "backend.services.quota_service.get_quota_status",
            new_callable=AsyncMock,
        ) as mock_qs:
            mock_qs.return_value = QuotaStatus(
                used_tokens=1_000_000,
                limit_tokens=1_000_000,
                remaining_tokens=0,
            )
            with pytest.raises(QuotaExceededError):
                await quota_guard(session=session, workspace_id=workspace_id)

    async def test_passes_with_minimal_remaining(self) -> None:
        """quota_guard should pass when remaining > 0, even if only 1 token."""
        from backend.api.dependencies import quota_guard

        session = AsyncMock()
        workspace_id = uuid.uuid4()

        with patch(
            "backend.services.quota_service.get_quota_status",
            new_callable=AsyncMock,
        ) as mock_qs:
            mock_qs.return_value = QuotaStatus(
                used_tokens=999_999,
                limit_tokens=1_000_000,
                remaining_tokens=1,
            )
            await quota_guard(session=session, workspace_id=workspace_id)
