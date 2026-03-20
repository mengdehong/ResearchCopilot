"""LangGraph Server HTTP client — mock implementation for MVP."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass(frozen=True)
class ThreadInfo:
    """Metadata returned when creating a thread."""

    thread_id: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RunInfo:
    """Metadata returned when creating or resuming a run."""

    run_id: str
    thread_id: str
    status: str = "pending"


class LangGraphClient:
    """LangGraph Server HTTP wrapper.

    MVP: mock implementation returning fake data.
    Phase 8: replace with real langgraph-sdk HTTP connection.
    """

    async def create_thread(self, *, metadata: dict[str, str] | None = None) -> ThreadInfo:
        """Create a new thread on LangGraph server."""
        return ThreadInfo(
            thread_id=str(uuid.uuid4()),
            metadata=metadata or {},
        )

    async def create_run(
        self,
        thread_id: str,
        *,
        assistant_id: str,
        input_data: dict,
        config: dict | None = None,
    ) -> RunInfo:
        """Submit a new run for the given thread."""
        return RunInfo(
            run_id=str(uuid.uuid4()),
            thread_id=thread_id,
            status="pending",
        )

    async def stream_run(
        self,
        thread_id: str,
        run_id: str,
    ) -> AsyncIterator[dict]:
        """Stream events from a running run.

        TODO(Phase 8): implement real SSE streaming from LangGraph server.
        """
        yield {
            "event": "events/metadata",
            "data": {"run_id": run_id, "thread_id": thread_id},
        }

    async def resume_run(
        self,
        thread_id: str,
        *,
        command: dict,
    ) -> RunInfo:
        """Resume a paused run with HITL response."""
        return RunInfo(
            run_id=str(uuid.uuid4()),
            thread_id=thread_id,
            status="resuming",
        )

    async def cancel_run(self, thread_id: str, run_id: str) -> None:
        """Cancel a running run."""

    async def get_thread_state(self, thread_id: str) -> dict:
        """Get current thread state snapshot."""
        return {"thread_id": thread_id, "values": {}, "next": []}
