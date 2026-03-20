"""Agent API router — thread runs, SSE events, and HITL interrupts."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.agent import InterruptResponse, RunRequest
from backend.models.thread import Thread
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo

router = APIRouter(prefix="/api/agent/threads", tags=["agent"])


async def _verify_thread_ownership(
    session: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
) -> Thread:
    """Verify that current_user owns the workspace containing the thread."""
    thread = await base_repo.get_by_id(session, Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    ws = await base_repo.get_by_id(session, Workspace, thread.workspace_id)
    if ws is None or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return thread


@router.post("/{thread_id}/runs", status_code=202)
async def create_run(
    thread_id: uuid.UUID,
    body: RunRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Trigger an agent run for the given thread.

    Returns 202 Accepted with run_id. The run executes asynchronously.
    TODO: integrate with agent_service to actually dispatch to LangGraph.
    """
    thread = await _verify_thread_ownership(session, thread_id, current_user)

    # TODO: dispatch to agent_service.submit_run(thread, body)
    return JSONResponse(
        status_code=501,
        content={
            "detail": "Agent run dispatch not yet implemented",
            "thread_id": str(thread.id),
        },
    )


@router.get("/{thread_id}/events")
async def stream_events(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """SSE event stream for agent run progress.

    TODO: implement SSE streaming via agent_service.stream_events().
    """
    await _verify_thread_ownership(session, thread_id, current_user)

    return JSONResponse(
        status_code=501,
        content={"detail": "SSE event streaming not yet implemented"},
    )


@router.post("/{thread_id}/interrupt")
async def respond_to_interrupt(
    thread_id: uuid.UUID,
    body: InterruptResponse,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Human-in-the-loop: respond to an agent interrupt.

    TODO: integrate with agent_service.resume_interrupt().
    """
    await _verify_thread_ownership(session, thread_id, current_user)

    return JSONResponse(
        status_code=501,
        content={"detail": "HITL interrupt response not yet implemented"},
    )
