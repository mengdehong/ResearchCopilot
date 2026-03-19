"""Quota record repository — pure functions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.quota_record import QuotaRecord


async def get_monthly_usage(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> int:
    """Sum total tokens (input + output) for the current month."""
    now = datetime.now(tz=UTC)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    stmt = select(
        func.coalesce(
            func.sum(QuotaRecord.input_tokens + QuotaRecord.output_tokens),
            0,
        ),
    ).where(
        QuotaRecord.workspace_id == workspace_id,
        QuotaRecord.created_at >= start_of_month,
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())
