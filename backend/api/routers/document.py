"""Document API router — upload, confirm, CRUD, retry, delete."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.document import DocumentCreate, DocumentMeta, DocumentStatus
from backend.clients.storage_client import StorageClient
from backend.models.user import User
from backend.services import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_storage() -> StorageClient:
    return StorageClient()


@router.post("/upload-url", status_code=201)
async def initiate_upload(
    body: DocumentCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageClient = Depends(_get_storage),
) -> dict:
    """Generate pre-signed upload URL and create document record."""
    result = await document_service.initiate_upload(
        session,
        storage,
        workspace_id=body.workspace_id,
        title=body.title,
        content_type=body.file_path,  # reuse field as content_type for now
        owner=current_user,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await session.commit()
    return {
        "document_id": str(result.document_id),
        "upload_url": result.upload_url,
        "storage_key": result.storage_key,
    }


@router.post("/confirm", response_model=DocumentMeta)
async def confirm_upload(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageClient = Depends(_get_storage),
) -> DocumentMeta:
    """Confirm upload completed, start parsing."""
    doc = await document_service.confirm_upload(
        session,
        storage,
        document_id=document_id,
        owner=current_user,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.commit()
    return DocumentMeta.model_validate(doc)


@router.get("", response_model=list[DocumentMeta])
async def list_documents(
    workspace_id: uuid.UUID,
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentMeta]:
    """List documents in a workspace."""
    docs = await document_service.list_documents(
        session,
        workspace_id,
        current_user,
        status_filter=status_filter,
    )
    if docs is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return [DocumentMeta.model_validate(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentMeta)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentMeta:
    """Get document by ID."""
    doc = await document_service.get_document(session, document_id, current_user)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentMeta.model_validate(doc)


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_document_status(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentStatus:
    """Get document parse status."""
    doc = await document_service.get_document(session, document_id, current_user)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatus.model_validate(doc)


@router.get("/{document_id}/artifacts")
async def get_document_artifacts(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get parsed artifacts (paragraphs, figures, etc.) for a document."""
    result = await document_service.get_document_artifacts(
        session,
        document_id,
        current_user,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": str(document_id), **result}


@router.post("/{document_id}/retry", response_model=DocumentMeta)
async def retry_parse(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentMeta:
    """Retry parsing a failed document."""
    doc = await document_service.retry_parse(session, document_id, current_user)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.commit()
    return DocumentMeta.model_validate(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageClient = Depends(_get_storage),
) -> None:
    """Delete a document and its storage object."""
    ok = await document_service.delete_document(
        session,
        storage,
        document_id=document_id,
        owner=current_user,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.commit()
