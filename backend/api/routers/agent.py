import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import (
    get_current_user,
    get_current_user_sse,
    get_db,
    get_lg_runner,
)
from backend.api.schemas.agent import InterruptResponse, RunRequest
from backend.clients.langgraph_runner import LangGraphRunner
from backend.core.logger import get_logger
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import run_snapshot_repo, thread_repo
from backend.services import agent_service
from backend.services.event_translator import translate_to_run_event

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agent/threads", tags=["agent"])


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
) -> dict:
    """Create a new agent thread."""
    thread = await agent_service.create_thread(
        session,
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
    runner: LangGraphRunner = Depends(get_lg_runner),
) -> dict:
    """Trigger an agent run."""
    result = await agent_service.trigger_run(
        session,
        runner,
        thread_id=thread_id,
        message=body.message,
        owner=current_user,
        discipline=body.discipline,
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
    current_user: User = Depends(get_current_user_sse),
    runner: LangGraphRunner = Depends(get_lg_runner),
) -> StreamingResponse:
    """SSE event stream for agent run progress.

    使用 get_current_user_sse 同时支持 Authorization header
    和 query param ?token=xxx（EventSource 无法设置 header）。
    """
    await _verify_thread_ownership(session, thread_id, current_user)

    async def event_generator():
        raw_stream = runner.get_event_stream(run_id)
        seq = 0
        completed_nodes: list[str] = []
        last_ai_content: str | None = None
        async for raw_event in raw_stream:
            # 检查 on_chain_end 的 output 中是否有新增 AI 消息
            # 仅限 supervisor 节点产出的 AIMessage（chat 模式），
            # 避免未来 workflow 子图意外覆盖
            raw_type = raw_event.get("event", "")
            if raw_type in ("on_chain_end", "events/on_chain_end"):
                raw_name = raw_event.get("name", "")
                output = raw_event.get("data", {}).get("output", {})
                if raw_name == "supervisor" and isinstance(output, dict):
                    msgs = output.get("messages", [])
                    for msg in reversed(msgs):
                        if hasattr(msg, "type") and msg.type == "ai":
                            last_ai_content = msg.content
                            break

            # 翻译事件
            run_event = translate_to_run_event(raw_event)
            if run_event is None:
                continue

            seq += 1
            event_type = run_event["event_type"]
            if event_type == "node_end":
                node_name = run_event["data"].get("node_name", "")
                if node_name:
                    completed_nodes.append(node_name)
            logger.debug(
                "sse_event_yielded",
                run_id=run_id,
                seq=seq,
                event_type=event_type,
            )
            yield f"id: {seq}\ndata: {json.dumps(run_event)}\n\n"

        # 发送 assistant_message：
        # 优先使用图执行产生的 AI 消息（supervisor chat 模式），
        # 否则回退到节点完成摘要
        seq += 1
        if last_ai_content:
            msg_event = {
                "event_type": "assistant_message",
                "data": {"content": last_ai_content},
            }
        elif completed_nodes:
            summary = " → ".join(completed_nodes)
            msg_event = {
                "event_type": "assistant_message",
                "data": {"content": f"已完成工作流：{summary}"},
            }
        else:
            msg_event = None

        if msg_event:
            yield f"id: {seq}\ndata: {json.dumps(msg_event)}\n\n"

        # 发送 run_end 信号让前端关闭连接
        seq += 1
        end_event = {"event_type": "run_end", "data": {"run_id": run_id}}
        yield f"id: {seq}\ndata: {json.dumps(end_event)}\n\n"
        logger.info("sse_stream_ended", run_id=run_id, event_count=seq)

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
) -> dict:
    """Resume a paused run with HITL response (placeholder)."""
    await _verify_thread_ownership(session, thread_id, current_user)
    return {"run_id": run_id, "status": "not_implemented"}


@router.post("/{thread_id}/runs/{run_id}/cancel", status_code=204)
async def cancel_run(
    thread_id: uuid.UUID,
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    runner: LangGraphRunner = Depends(get_lg_runner),
) -> None:
    """Cancel a running run."""
    ok = await agent_service.cancel_run(
        session,
        runner,
        thread_id=thread_id,
        run_id=run_id,
        owner=current_user,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
