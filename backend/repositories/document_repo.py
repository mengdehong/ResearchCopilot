"""Document repository — pure functions."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import InvalidStateTransitionError
from backend.models.document import Document

# Valid parse_status transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "uploading": {"pending"},
    "pending": {"parsing", "failed"},
    "parsing": {"completed", "failed"},
    "failed": {"pending"},  # retry allowed
}


@dataclass(frozen=True)
class DocStatusCounts:
    """Aggregated document status counts for a workspace."""

    uploading: int = 0
    pending: int = 0
    parsing: int = 0
    completed: int = 0
    failed: int = 0


async def list_by_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    status_filter: str | None = None,
) -> list[Document]:
    """List all documents in a workspace, optionally filtered by parse_status."""
    stmt = select(Document).where(Document.workspace_id == workspace_id)
    if status_filter is not None:
        stmt = stmt.where(Document.parse_status == status_filter)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_parse_status(
    session: AsyncSession,
    document: Document,
    status: str,
) -> None:
    """Update the parse_status field with state transition guard."""
    current = document.parse_status
    allowed = _VALID_TRANSITIONS.get(current, set())
    if status not in allowed:
        raise InvalidStateTransitionError(f"Cannot transition from '{current}' to '{status}'")
    document.parse_status = status
    await session.flush()


async def count_by_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> DocStatusCounts:
    """Count documents grouped by parse_status in a workspace."""
    stmt = (
        select(Document.parse_status, func.count())
        .where(Document.workspace_id == workspace_id)
        .group_by(Document.parse_status)
    )
    result = await session.execute(stmt)
    counts: dict[str, int] = {}
    for status, count in result.all():
        counts[status] = count
    return DocStatusCounts(**counts)
