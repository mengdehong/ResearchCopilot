"""Agent schemas — run request/event DTOs (stub, pending P2 completion)."""

import uuid

from pydantic import BaseModel


class RunRequest(BaseModel):
    """Trigger an agent run.

    # TODO(P2): replace stub with full implementation after agent_service is ready.
    """

    message: str
    editor_content: str | None = None
    attachment_ids: list[uuid.UUID] | None = None


class RunEvent(BaseModel):
    """SSE event from agent run.

    # TODO(P2): replace stub with full SSE event schema.
    """

    event_type: str
    data: dict[str, str | int | bool | None]


class InterruptResponse(BaseModel):
    """Human-in-the-loop response to agent interrupt.

    # TODO(P2): replace stub with full HITL schema.
    """

    action: str
    feedback: str | None = None
