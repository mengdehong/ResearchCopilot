"""Document API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.document import DocumentCreate, DocumentMeta, DocumentStatus
from backend.models.document import Document
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", status_code=201, response_model=DocumentMeta)
async def create_document(
    body: DocumentCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentMeta:
    """Create document metadata record."""
    # Verify workspace ownership
    ws = await base_repo.get_by_id(session, Workspace, body.workspace_id)
    if ws is None or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    doc = Document()
    doc.workspace_id = body.workspace_id
    doc.title = body.title
    doc.file_path = body.file_path
    doc.doi = body.doi
    doc.abstract_text = body.abstract_text
    doc.year = body.year
    doc.source = body.source
    doc.include_appendix = body.include_appendix
    doc.parse_status = "pending"

    created = await base_repo.create(session, doc)
    await session.commit()
    return DocumentMeta.model_validate(created)


@router.get("/{document_id}", response_model=DocumentMeta)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentMeta:
    """Get document metadata by ID."""
    doc = await base_repo.get_by_id(session, Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify workspace ownership
    ws = await base_repo.get_by_id(session, Workspace, doc.workspace_id)
    if ws is None or ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return DocumentMeta.model_validate(doc)


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_document_status(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentStatus:
    """Get document parse status."""
    doc = await base_repo.get_by_id(session, Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify workspace ownership
    ws = await base_repo.get_by_id(session, Workspace, doc.workspace_id)
    if ws is None or ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return DocumentStatus.model_validate(doc)
