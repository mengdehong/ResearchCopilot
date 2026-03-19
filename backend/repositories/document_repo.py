"""Document repository — pure functions."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.document import Document


async def list_by_workspace(
    session: AsyncSession, workspace_id: uuid.UUID,
) -> list[Document]:
    """List all documents in a workspace."""
    stmt = select(Document).where(Document.workspace_id == workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_parse_status(
    session: AsyncSession, document: Document, status: str,
) -> None:
    """Update the parse_status field and flush."""
    document.parse_status = status
    await session.flush()
