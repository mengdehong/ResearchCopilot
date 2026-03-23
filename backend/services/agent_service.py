"""Agent service — BFF business logic for agent run lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage

from backend.models.run_snapshot import RunSnapshot
from backend.models.thread import Thread
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.clients.langgraph_runner import LangGraphRunner
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
    *,
    workspace_id: uuid.UUID,
    title: str,
    owner: User,
) -> Thread | None:
    """Create a local thread (no external LangGraph server needed)."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != owner.id:
        return None

    thread = Thread()
    thread.workspace_id = workspace_id
    thread.title = title
    thread.status = "idle"
    return await base_repo.create(session, thread)


async def trigger_run(
    session: AsyncSession,
    runner: LangGraphRunner,
    *,
    thread_id: uuid.UUID,
    message: str,
    owner: User,
    workspace_id: str | None = None,
    discipline: str | None = None,
    auth_token: str | None = None,
    editor_content: str | None = None,
    attachment_ids: list[uuid.UUID] | None = None,
) -> RunResult | None:
    """Store snapshot → start graph execution via Runner → return run_id."""
    thread = await _verify_thread_ownership(session, thread_id, owner)
    if thread is None:
        return None

    run_id = str(uuid.uuid4())

    # Store input snapshot
    snapshot = RunSnapshot()
    snapshot.thread_id = thread_id
    snapshot.run_id = uuid.UUID(run_id)
    snapshot.user_message = message
    snapshot.status = "running"
    await base_repo.create(session, snapshot)

    # Build graph input (SharedState fields)
    input_data: dict = {
        "messages": [HumanMessage(content=message)],
        "workspace_id": workspace_id or str(thread.workspace_id),
        "discipline": discipline or "",
        "artifacts": {},
    }
    if editor_content is not None:
        input_data["editor_content"] = editor_content
    if attachment_ids is not None:
        input_data["attachment_ids"] = [str(aid) for aid in attachment_ids]

    config = {
        "configurable": {
            "thread_id": str(thread_id),
            "run_id": run_id,
        }
    }
    if auth_token:
        config["configurable"]["auth_token"] = auth_token

    # Start real graph execution
    await runner.start_run(
        run_id=run_id,
        thread_id=str(thread_id),
        input_data=input_data,
        config=config,
    )

    return RunResult(
        run_id=run_id,
        thread_id=str(thread_id),
        status="running",
        stream_url=f"/api/v1/agent/threads/{thread_id}/runs/{run_id}/stream",
    )


async def cancel_run(
    session: AsyncSession,
    runner: LangGraphRunner,
    *,
    thread_id: uuid.UUID,
    run_id: str,
    owner: User,
) -> bool:
    """Cancel a running run."""
    thread = await _verify_thread_ownership(session, thread_id, owner)
    if thread is None:
        return False

    await runner.cancel_run(run_id)
    return True


async def update_thread_status(
    session: AsyncSession,
    thread_id: uuid.UUID,
    status: str,
) -> None:
    """更新 Thread 状态。"""
    thread = await base_repo.get_by_id(session, Thread, thread_id)
    if thread is not None:
        thread.status = status
        await session.flush()
