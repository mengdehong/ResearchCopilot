"""Document service — BFF business logic for upload, parsing, retrieval."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.core.exceptions import UploadNotFoundError
from backend.models.document import Document
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import document_repo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.clients.storage_client import StorageClient
    from backend.models.user import User


@dataclass(frozen=True)
class UploadInitResult:
    """Result of initiating a document upload."""

    document_id: uuid.UUID
    upload_url: str
    storage_key: str


async def _verify_workspace_ownership(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner: User,
) -> Workspace | None:
    """Verify workspace ownership. Returns None if not found or forbidden."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != owner.id:
        return None
    return ws


async def initiate_upload(
    session: AsyncSession,
    storage: StorageClient,
    *,
    workspace_id: uuid.UUID,
    title: str,
    content_type: str,
    owner: User,
) -> UploadInitResult | None:
    """Create document record + generate pre-signed upload URL."""
    ws = await _verify_workspace_ownership(session, workspace_id, owner)
    if ws is None:
        return None

    storage_key = f"workspaces/{workspace_id}/documents/{uuid.uuid4()}.pdf"
    upload_url = await storage.generate_upload_url(storage_key, content_type)

    doc = Document()
    doc.workspace_id = workspace_id
    doc.title = title
    doc.file_path = storage_key
    doc.parse_status = "uploading"
    doc.source = "upload"
    doc.include_appendix = False
    created = await base_repo.create(session, doc)

    return UploadInitResult(
        document_id=created.id,
        upload_url=upload_url,
        storage_key=storage_key,
    )


async def confirm_upload(
    session: AsyncSession,
    storage: StorageClient,
    *,
    document_id: uuid.UUID,
    owner: User,
) -> Document | None:
    """Confirm upload completed: verify object exists, update status."""
    doc = await base_repo.get_by_id(session, Document, document_id)
    if doc is None:
        return None

    ws = await _verify_workspace_ownership(session, doc.workspace_id, owner)
    if ws is None:
        return None

    exists = await storage.head_object(doc.file_path)
    if not exists:
        raise UploadNotFoundError()

    await document_repo.update_parse_status(session, doc, "pending")

    from backend.workers.celery_app import celery_app

    celery_app.send_task(
        "backend.workers.tasks.parse_document.run_parse_pipeline",
        kwargs={"doc_id": str(doc.id)},
    )
    return doc


async def list_documents(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner: User,
    *,
    status_filter: str | None = None,
) -> list[Document] | None:
    """List documents in a workspace. Returns None if workspace not owned."""
    ws = await _verify_workspace_ownership(session, workspace_id, owner)
    if ws is None:
        return None
    return await document_repo.list_by_workspace(
        session,
        workspace_id,
        status_filter=status_filter,
    )


async def get_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    owner: User,
) -> Document | None:
    """Get a document by ID with ownership verification."""
    doc = await base_repo.get_by_id(session, Document, document_id)
    if doc is None:
        return None
    ws = await _verify_workspace_ownership(session, doc.workspace_id, owner)
    if ws is None:
        return None
    return doc


async def retry_parse(
    session: AsyncSession,
    document_id: uuid.UUID,
    owner: User,
) -> Document | None:
    """Retry parsing a failed document (failed→pending)."""
    doc = await get_document(session, document_id, owner)
    if doc is None:
        return None
    await document_repo.update_parse_status(session, doc, "pending")
    # TODO: trigger Celery parse task
    return doc


async def delete_document(
    session: AsyncSession,
    storage: StorageClient,
    *,
    document_id: uuid.UUID,
    owner: User,
) -> bool:
    """Delete a document and its storage object."""
    doc = await get_document(session, document_id, owner)
    if doc is None:
        return False
    await storage.delete_object(doc.file_path)
    await session.delete(doc)
    await session.flush()
    return True
