"""Agent API router — thread CRUD, runs, SSE events, HITL interrupts."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.agent import InterruptResponse, RunRequest
from backend.clients.langgraph_client import LangGraphClient
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import run_snapshot_repo, thread_repo
from backend.services import agent_service
from backend.services.event_translator import translate_sse_stream

router = APIRouter(prefix="/api/agent/threads", tags=["agent"])


def _get_lg_client() -> LangGraphClient:
    return LangGraphClient()


async def _verify_thread_ownership(
    session: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
) -> None:
    """Verify thread→workspace→owner chain. Raises 404/403 on failure."""
    thread = await thread_repo.get_by_id(session, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    ws = await base_repo.get_by_id(session, Workspace, thread.workspace_id)
    if ws is None or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("", status_code=201)
async def create_thread(
    workspace_id: uuid.UUID,
    title: str = "New Thread",
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    lg_client: LangGraphClient = Depends(_get_lg_client),
) -> dict:
    """Create a new agent thread."""
    thread = await agent_service.create_thread(
        session,
        lg_client,
        workspace_id=workspace_id,
        title=title,
        owner=current_user,
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await session.commit()
    return {
        "thread_id": str(thread.id),
        "workspace_id": str(thread.workspace_id),
        "title": thread.title,
        "status": thread.status,
        "langgraph_thread_id": thread.langgraph_thread_id,
    }


@router.get("")
async def list_threads(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List threads in a workspace."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    threads = await thread_repo.list_by_workspace(session, workspace_id)
    return [
        {
            "thread_id": str(t.id),
            "title": t.title,
            "status": t.status,
        }
        for t in threads
    ]


@router.get("/{thread_id}")
async def get_thread(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get thread details."""
    await _verify_thread_ownership(session, thread_id, current_user)
    thread = await thread_repo.get_by_id(session, thread_id)
    return {
        "thread_id": str(thread.id),
        "title": thread.title,
        "status": thread.status,
    }


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a thread."""
    await _verify_thread_ownership(session, thread_id, current_user)
    thread = await thread_repo.get_by_id(session, thread_id)
    await session.delete(thread)
    await session.commit()


@router.post("/{thread_id}/runs", status_code=202)
async def create_run(
    thread_id: uuid.UUID,
    body: RunRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    lg_client: LangGraphClient = Depends(_get_lg_client),
) -> dict:
    """Trigger an agent run."""
    result = await agent_service.trigger_run(
        session,
        lg_client,
        thread_id=thread_id,
        message=body.message,
        owner=current_user,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await session.commit()
    return {
        "run_id": result.run_id,
        "thread_id": result.thread_id,
        "status": result.status,
        "stream_url": result.stream_url,
    }


@router.get("/{thread_id}/runs")
async def list_runs(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List runs for a thread."""
    await _verify_thread_ownership(session, thread_id, current_user)
    snapshots = await run_snapshot_repo.list_by_thread(session, thread_id)
    return [
        {
            "run_id": str(s.run_id),
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in snapshots
    ]


@router.get("/{thread_id}/runs/{run_id}")
async def get_run(
    thread_id: uuid.UUID,
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get run details."""
    await _verify_thread_ownership(session, thread_id, current_user)
    snapshot = await run_snapshot_repo.get_by_run_id(session, uuid.UUID(run_id))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": str(snapshot.run_id),
        "thread_id": str(snapshot.thread_id),
        "status": snapshot.status,
        "user_message": snapshot.user_message,
        "tokens_used": snapshot.tokens_used,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "completed_at": snapshot.completed_at.isoformat() if snapshot.completed_at else None,
    }


@router.get("/{thread_id}/runs/{run_id}/stream")
async def stream_run_events(
    thread_id: uuid.UUID,
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    lg_client: LangGraphClient = Depends(_get_lg_client),
) -> StreamingResponse:
    """SSE event stream for agent run progress."""
    await _verify_thread_ownership(session, thread_id, current_user)
    thread = await thread_repo.get_by_id(session, thread_id)
    langgraph_thread_id = thread.langgraph_thread_id or str(thread_id)

    async def event_generator():
        raw_stream = lg_client.stream_run(langgraph_thread_id, run_id)
        async for sse_event in translate_sse_stream(raw_stream):
            data = sse_event.model_dump_json()
            yield f"event: {sse_event.event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{thread_id}/runs/{run_id}/resume")
async def resume_run(
    thread_id: uuid.UUID,
    run_id: str,
    body: InterruptResponse,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    lg_client: LangGraphClient = Depends(_get_lg_client),
) -> dict:
    """Resume a paused run with HITL response."""
    result = await agent_service.resume_run(
        session,
        lg_client,
        thread_id=thread_id,
        run_id=run_id,
        action=body.action,
        payload=body.payload,
        owner=current_user,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await session.commit()
    return {"run_id": result.run_id, "status": result.status}


@router.post("/{thread_id}/runs/{run_id}/cancel", status_code=204)
async def cancel_run(
    thread_id: uuid.UUID,
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    lg_client: LangGraphClient = Depends(_get_lg_client),
) -> None:
    """Cancel a running run."""
    ok = await agent_service.cancel_run(
        session,
        lg_client,
        thread_id=thread_id,
        run_id=run_id,
        owner=current_user,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
