"""Quota service — token consumption tracking and limit enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from backend.core.exceptions import QuotaExceededError
from backend.models.quota_record import QuotaRecord

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class QuotaStatus:
    """Current month's quota status for a user."""

    used_tokens: int
    limit_tokens: int
    remaining_tokens: int


# Default monthly limit per user (configurable via env in production)
DEFAULT_MONTHLY_LIMIT = 1_000_000


async def get_quota_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    monthly_limit: int = DEFAULT_MONTHLY_LIMIT,
) -> QuotaStatus:
    """Get current month's token usage and remaining quota."""
    now = datetime.now(tz=UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    stmt = select(
        func.coalesce(
            func.sum(QuotaRecord.input_tokens + QuotaRecord.output_tokens),
            0,
        ),
    ).where(
        QuotaRecord.workspace_id == workspace_id,
        QuotaRecord.created_at >= month_start,
    )
    result = await session.execute(stmt)
    used = result.scalar_one()

    return QuotaStatus(
        used_tokens=used,
        limit_tokens=monthly_limit,
        remaining_tokens=max(0, monthly_limit - used),
    )


async def check_and_consume(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    input_tokens: int,
    output_tokens: int,
    model_name: str,
    monthly_limit: int = DEFAULT_MONTHLY_LIMIT,
) -> QuotaRecord:
    """Check quota and record consumption. Raises QuotaExceededError if over limit."""
    total = input_tokens + output_tokens
    status = await get_quota_status(session, workspace_id, monthly_limit=monthly_limit)
    if status.remaining_tokens < total:
        raise QuotaExceededError()

    record = QuotaRecord()
    record.workspace_id = workspace_id
    record.run_id = run_id
    record.input_tokens = input_tokens
    record.output_tokens = output_tokens
    record.model_name = model_name
    session.add(record)
    await session.flush()
    return record
