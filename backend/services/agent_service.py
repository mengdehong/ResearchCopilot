"""Agent service — BFF business logic for agent run lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.models.run_snapshot import RunSnapshot
from backend.models.thread import Thread
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.clients.langgraph_client import LangGraphClient, RunInfo
    from backend.models.user import User


@dataclass(frozen=True)
class RunResult:
    """Result of triggering an agent run."""

    run_id: str
    thread_id: str
    status: str
    stream_url: str


async def _verify_thread_ownership(
    session: AsyncSession,
    thread_id: uuid.UUID,
    owner: User,
) -> Thread | None:
    """Verify thread→workspace→owner chain."""
    thread = await base_repo.get_by_id(session, Thread, thread_id)
    if thread is None:
        return None
    ws = await base_repo.get_by_id(session, Workspace, thread.workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != owner.id:
        return None
    return thread


async def create_thread(
    session: AsyncSession,
    lg_client: LangGraphClient,
    *,
    workspace_id: uuid.UUID,
    title: str,
    owner: User,
) -> Thread | None:
    """Create a local thread + corresponding thread on LangGraph."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != owner.id:
        return None

    lg_info = await lg_client.create_thread(
        metadata={"workspace_id": str(workspace_id)},
    )

    thread = Thread()
    thread.workspace_id = workspace_id
    thread.title = title
    thread.status = "creating"
    thread.langgraph_thread_id = lg_info.thread_id
    return await base_repo.create(session, thread)


async def trigger_run(
    session: AsyncSession,
    lg_client: LangGraphClient,
    *,
    thread_id: uuid.UUID,
    message: str,
    owner: User,
) -> RunResult | None:
    """Store snapshot → quota check → forward to LangGraph → return run_id."""
    thread = await _verify_thread_ownership(session, thread_id, owner)
    if thread is None:
        return None

    # Forward to LangGraph first to get run_id
    run_info: RunInfo = await lg_client.create_run(
        thread.langgraph_thread_id or str(thread_id),
        assistant_id="default",
        input_data={"message": message},
    )

    # Store input snapshot with run_id
    snapshot = RunSnapshot()
    snapshot.thread_id = thread_id
    snapshot.run_id = uuid.UUID(run_info.run_id)
    snapshot.user_message = message
    snapshot.status = "running"
    await base_repo.create(session, snapshot)

    return RunResult(
        run_id=run_info.run_id,
        thread_id=str(thread_id),
        status="running",
        stream_url=f"/api/agent/threads/{thread_id}/runs/{run_info.run_id}/stream",
    )


async def resume_run(
    session: AsyncSession,
    lg_client: LangGraphClient,
    *,
    thread_id: uuid.UUID,
    run_id: str,
    action: str,
    payload: dict | None,
    owner: User,
) -> RunResult | None:
    """Human-in-the-loop: resume a paused run with user response."""
    thread = await _verify_thread_ownership(session, thread_id, owner)
    if thread is None:
        return None

    command = {"resume": action}
    if payload:
        command["payload"] = payload

    run_info = await lg_client.resume_run(
        thread.langgraph_thread_id or str(thread_id),
        command=command,
    )

    return RunResult(
        run_id=run_info.run_id,
        thread_id=str(thread_id),
        status=run_info.status,
        stream_url=f"/api/agent/threads/{thread_id}/runs/{run_info.run_id}/stream",
    )


async def cancel_run(
    session: AsyncSession,
    lg_client: LangGraphClient,
    *,
    thread_id: uuid.UUID,
    run_id: str,
    owner: User,
) -> bool:
    """Cancel a running run."""
    thread = await _verify_thread_ownership(session, thread_id, owner)
    if thread is None:
        return False

    await lg_client.cancel_run(
        thread.langgraph_thread_id or str(thread_id),
        run_id,
    )
    return True
