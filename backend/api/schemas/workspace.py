"""Workspace schemas — request/response DTOs."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    """Create workspace request."""

    name: str = Field(..., min_length=1, max_length=200)
    discipline: str = Field(default="computer_science", max_length=100)


class WorkspaceDetail(BaseModel):
    """Workspace detail response."""

    id: uuid.UUID
    name: str
    discipline: str
    owner_id: uuid.UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceList(BaseModel):
    """Workspace list response wrapper."""

    items: list[WorkspaceDetail]
    total: int
