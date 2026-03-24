"""Document schemas — request/response DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """Create document metadata request."""

    title: str = Field(..., min_length=1, max_length=500)
    file_path: str = Field(..., min_length=1)
    workspace_id: uuid.UUID
    doi: str | None = None
    abstract_text: str | None = None
    year: int | None = None
    source: str = "upload"
    include_appendix: bool = False


class DocumentMeta(BaseModel):
    """Document metadata response."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    file_path: str
    parse_status: str
    source: str
    doi: str | None
    abstract_text: str | None
    year: int | None
    include_appendix: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatus(BaseModel):
    """Document parse status response."""

    id: uuid.UUID
    parse_status: str
    updated_at: datetime

    model_config = {"from_attributes": True}
