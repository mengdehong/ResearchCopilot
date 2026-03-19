"""Editor schemas — draft save/load DTOs."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class DraftSave(BaseModel):
    """Save editor draft request."""

    content: str


class DraftLoad(BaseModel):
    """Load editor draft response."""

    thread_id: uuid.UUID
    content: str
    updated_at: datetime

    model_config = {"from_attributes": True}
