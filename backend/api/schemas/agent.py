"""Agent schemas — run request/event DTOs。"""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Trigger an agent run."""

    message: str
    editor_content: str | None = None
    attachment_ids: list[uuid.UUID] | None = None
    discipline: str | None = None


class RunEvent(BaseModel):
    """SSE event from agent run (simplified for API response)."""

    seq: int
    event_type: str
    timestamp: str
    payload: dict[str, Any]


class InterruptResponse(BaseModel):
    """Human-in-the-loop response to agent interrupt."""

    action: str = Field(
        ...,
        description="approve | reject | select",
    )
    feedback: str | None = None
    payload: dict[str, Any] | None = None
    selected_ids: list[str] | None = None


class RunSummary(BaseModel):
    """Run list item."""

    run_id: str
    status: str
    created_at: str | None = None
    completed_at: str | None = None


class RunDetail(BaseModel):
    """Detailed run information."""

    run_id: str
    thread_id: str
    status: str
    user_message: str | None = None
    editor_content: str | None = None
    tokens_used: int | None = None
    created_at: str | None = None
    completed_at: str | None = None
