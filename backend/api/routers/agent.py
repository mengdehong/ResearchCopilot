import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import (
    get_current_user,
    get_current_user_or_system,
    get_current_user_sse,
    get_db,
    get_lg_runner,
)
from backend.api.rate_limit import _settings as _rate_limit_settings
from backend.api.rate_limit import get_user_id_or_ip, limiter
from backend.api.schemas.agent import InterruptResponse, RunRequest
from backend.clients.langgraph_runner import LangGraphRunner
from backend.core.logger import get_logger
from backend.models.editor_draft import EditorDraft
from backend.models.run_snapshot import RunSnapshot
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.repositories import base as base_repo
from backend.repositories import run_snapshot_repo, thread_repo
from backend.services import agent_service
from backend.services.artifacts_renderer import render_artifacts
from backend.services.event_translator import translate_to_run_event

logger = get_logger(__name__)

_WF_NAMES: frozenset[str] = frozenset(
    {"discovery", "extraction", "ideation", "execution", "critique", "publish"}
)


def _build_content_block_event(node_name: str, markdown: str) -> dict:
    """Build a content_block SSE event dict."""
    return {
        "event_type": "content_block",
        "data": {"content": markdown, "workflow": node_name},
    }


def _build_sandbox_event(wf_artifacts: dict) -> dict:
    """Build a sandbox_result SSE event dict from execution workflow artifacts."""
    exec_results = wf_artifacts.get("results", {})
    return {
        "event_type": "sandbox_result",
        "data": {
            "code": wf_artifacts.get("code", ""),
            "stdout": exec_results.get("stdout", ""),
            "stderr": exec_results.get("stderr", ""),
            "exit_code": exec_results.get("exit_code", -1),
            "duration_ms": 0,
            "artifacts": wf_artifacts.get("output_files", []),
        },
    }


def _build_assistant_message_event(
    last_ai_content: str | None,
    completed_nodes: list[str],
) -> dict | None:
    """Build an assistant_message SSE event dict, or None if there is nothing to say."""
    if last_ai_content:
        return {"event_type": "assistant_message", "data": {"content": last_ai_content}}
    if completed_nodes:
        summary = " → ".join(completed_nodes)
        return {"event_type": "assistant_message", "data": {"content": f"已完成工作流：{summary}"}}
    return None


router = APIRouter(prefix="/agent/threads", tags=["agent"])


def _normalize_pending_interrupt(interrupt_data: dict | None) -> dict | None:
    """Normalize persisted interrupt payload to the frontend InterruptData shape."""
    if interrupt_data is None:
        return None
    if "payload" in interrupt_data and isinstance(interrupt_data["payload"], dict):
        return interrupt_data

    payload = {
        key: value
        for key, value in interrupt_data.items()
        if key not in {"action", "run_id", "thread_id"}
    }
    return {
        "action": interrupt_data.get("action", "confirm_execute"),
        "run_id": interrupt_data.get("run_id", ""),
        "thread_id": interrupt_data.get("thread_id", ""),
        "payload": payload,
    }


def _determine_terminal_status(
    *,
    existing_status: str | None,
    was_interrupted: bool,
    saw_error_event: bool,
) -> str:
    """Resolve the final persisted run status without clobbering terminal states."""
    if existing_status in {"cancelled", "failed"}:
        return existing_status
    if was_interrupted:
        return "interrupted"
    if saw_error_event:
        return "failed"
    return "completed"


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
    limit: int | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List threads in a workspace."""
    ws = await base_repo.get_by_id(session, Workspace, workspace_id)
    if ws is None or ws.is_deleted or ws.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    threads = await thread_repo.list_by_workspace(session, workspace_id, limit=limit)
    return [
        {
            "thread_id": str(t.id),
            "title": t.title,
            "status": t.status,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
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
    active_snap = await run_snapshot_repo.get_active_by_thread(session, thread_id)
    return {
        "thread_id": str(thread.id),
        "title": thread.title,
        "status": thread.status,
        "active_run_id": str(active_snap.run_id) if active_snap else None,
    }


@router.get("/{thread_id}/messages")
async def get_thread_messages(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """从 RunSnapshot 重建 thread 的聊天历史。"""
    await _verify_thread_ownership(session, thread_id, current_user)
    snapshots = await run_snapshot_repo.list_by_thread(session, thread_id)
    # list_by_thread 返回 created_at DESC，这里需要正序
    snapshots.reverse()
    messages: list[dict] = []
    for snap in snapshots:
        messages.append(
            {
                "id": str(snap.run_id),
                "role": "user",
                "content": snap.user_message,
                "timestamp": snap.created_at.isoformat() if snap.created_at else None,
            }
        )
        # 如果有 assistant 回复，添加 assistant 消息
        if snap.assistant_response:
            assistant_msg: dict = {
                "id": f"{snap.run_id}-reply",
                "role": "assistant",
                "content": snap.assistant_response,
                "timestamp": (snap.completed_at or snap.created_at).isoformat()
                if (snap.completed_at or snap.created_at)
                else None,
            }
            if snap.cot_nodes:
                assistant_msg["cotNodes"] = snap.cot_nodes
            messages.append(assistant_msg)

    pending_interrupt: dict | None = None
    last_snap = snapshots[-1] if snapshots else None
    if last_snap and last_snap.status == "interrupted" and last_snap.interrupt_data:
        pending_interrupt = _normalize_pending_interrupt(last_snap.interrupt_data)

    return {
        "messages": messages,
        "pending_interrupt": pending_interrupt,
        "cot_nodes": last_snap.cot_nodes if last_snap else None,
    }


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a thread and all related data."""
    await _verify_thread_ownership(session, thread_id, current_user)

    # 手动清理关联数据（兜底，防止旧表缺少 CASCADE 约束）
    await session.execute(sa_delete(RunSnapshot).where(RunSnapshot.thread_id == thread_id))
    await session.execute(sa_delete(EditorDraft).where(EditorDraft.thread_id == thread_id))

    thread = await thread_repo.get_by_id(session, thread_id)
    await session.delete(thread)
    await session.commit()


@router.post("/{thread_id}/runs", status_code=202)
@limiter.limit(_rate_limit_settings.rate_limit_agent_run, key_func=get_user_id_or_ip)
async def create_run(
    request: Request,
    thread_id: uuid.UUID,
    body: RunRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    runner: LangGraphRunner = Depends(get_lg_runner),
) -> dict:
    """Trigger an agent run."""
    auth_token = request.headers.get("Authorization")

    result = await agent_service.trigger_run(
        session,
        runner,
        thread_id=thread_id,
        message=body.message,
        owner=current_user,
        discipline=body.discipline,
        auth_token=auth_token,
        editor_content=body.editor_content,
        attachment_ids=body.attachment_ids,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    await agent_service.update_thread_status(session, thread_id, "running")
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
@limiter.limit(_rate_limit_settings.rate_limit_agent_sse, key_func=get_user_id_or_ip)
async def stream_run_events(
    request: Request,
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
        seq = 0
        completed_nodes: list[str] = []
        cot_entries: list[dict] = []
        last_ai_content: str | None = None
        was_interrupted = False
        saw_error_event = False
        interrupt_payload_for_db: dict | None = None
        content_blocks_for_db: list[dict] = []
        try:
            raw_stream = runner.get_event_stream(run_id)
            async for raw_event in raw_stream:
                # 捕获 supervisor 节点产出的 AIMessage（chat 模式），供后续 assistant_message 使用
                raw_type = raw_event.get("event", "")
                if raw_type in ("on_chain_end", "events/on_chain_end"):
                    output = raw_event.get("data", {}).get("output", {})
                    if raw_event.get("name") == "supervisor" and isinstance(output, dict):
                        for msg in reversed(output.get("messages", [])):
                            if hasattr(msg, "type") and msg.type == "ai":
                                last_ai_content = msg.content
                                break

                run_event = translate_to_run_event(raw_event)
                if run_event is None:
                    continue

                seq += 1
                event_type = run_event["event_type"]
                node_name = run_event["data"].get("node_name", "")
                if event_type == "node_start" and node_name:
                    cot_entries.append({"name": node_name, "start_ms": 0, "status": "running"})
                if event_type == "node_end" and node_name:
                    completed_nodes.append(node_name)
                    for entry in cot_entries:
                        if entry["name"] == node_name and entry["status"] == "running":
                            entry["status"] = "completed"
                            break
                if event_type == "interrupt":
                    was_interrupted = True
                    interrupt_payload_for_db = run_event["data"]
                if event_type == "error":
                    saw_error_event = True
                logger.debug(
                    "sse_event_yielded",
                    run_id=run_id,
                    seq=seq,
                    event_type=event_type,
                )
                yield f"id: {seq}\ndata: {json.dumps(run_event)}\n\n"

                # WF 子图完成后注入 content_block 与（可选）sandbox_result
                if event_type == "node_end" and node_name in _WF_NAMES:
                    raw_output = raw_event.get("data", {}).get("output", {})
                    wf_artifacts = (
                        raw_output.get("artifacts", {}).get(node_name, {})
                        if isinstance(raw_output, dict)
                        else {}
                    )
                    markdown = render_artifacts(node_name, wf_artifacts)
                    if markdown:
                        content_blocks_for_db.append({"content": markdown, "workflow": node_name})
                        seq += 1
                        content_event = _build_content_block_event(node_name, markdown)
                        logger.debug(
                            "sse_content_block_injected",
                            run_id=run_id,
                            workflow=node_name,
                            content_length=len(markdown),
                        )
                        yield f"id: {seq}\ndata: {json.dumps(content_event)}\n\n"

                    if node_name == "execution" and wf_artifacts:
                        seq += 1
                        sandbox_event = _build_sandbox_event(wf_artifacts)
                        logger.debug(
                            "sse_sandbox_result_injected",
                            run_id=run_id,
                            exit_code=wf_artifacts.get("results", {}).get("exit_code"),
                        )
                        yield f"id: {seq}\ndata: {json.dumps(sandbox_event)}\n\n"

            # interrupt 时不发 assistant_message，前端会显示 HITL 卡片
            if not was_interrupted:
                msg_event = _build_assistant_message_event(last_ai_content, completed_nodes)
                if msg_event:
                    seq += 1
                    yield f"id: {seq}\ndata: {json.dumps(msg_event)}\n\n"

        except Exception as exc:
            saw_error_event = True
            logger.error(
                "sse_stream_error", run_id=run_id, error=str(exc), error_type=type(exc).__name__
            )
            seq += 1
            error_event = {
                "event_type": "error",
                "data": {
                    "message": "Stream interrupted due to an internal error",
                    "error_type": "INTERNAL_ERROR",
                },
            }
            yield f"id: {seq}\ndata: {json.dumps(error_event)}\n\n"
        finally:
            assistant_text = last_ai_content or (
                f"已完成工作流：{' → '.join(completed_nodes)}" if completed_nodes else None
            )
            try:
                factory = request.app.state.session_factory
                async with factory() as db:
                    snap = await run_snapshot_repo.get_by_run_id(db, uuid.UUID(run_id))
                    if snap:
                        if assistant_text:
                            snap.assistant_response = assistant_text
                        snap.status = _determine_terminal_status(
                            existing_status=snap.status,
                            was_interrupted=was_interrupted,
                            saw_error_event=saw_error_event,
                        )
                        snap.completed_at = datetime.utcnow()
                        if interrupt_payload_for_db:
                            snap.interrupt_data = interrupt_payload_for_db
                        if cot_entries:
                            snap.cot_nodes = cot_entries
                        elif completed_nodes:
                            snap.cot_nodes = [
                                {"name": node_name, "status": "completed"}
                                for node_name in completed_nodes
                            ]
                        if content_blocks_for_db:
                            snap.content_blocks = content_blocks_for_db
                        await db.commit()
            except Exception as save_exc:
                logger.warning(
                    "run_snapshot_save_failed",
                    run_id=run_id,
                    error=str(save_exc),
                )
            try:
                factory = request.app.state.session_factory
                async with factory() as db:
                    new_status = "interrupted" if was_interrupted else "idle"
                    await agent_service.update_thread_status(db, thread_id, new_status)
                    await db.commit()
            except Exception as ts_exc:
                logger.warning(
                    "thread_status_update_failed",
                    run_id=run_id,
                    thread_id=str(thread_id),
                    error=str(ts_exc),
                )
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
    current_user: User | None = Depends(get_current_user_or_system),
    runner: LangGraphRunner = Depends(get_lg_runner),
) -> dict:
    """Resume a paused run with HITL response."""
    # 系统调用跳过 ownership 检查
    if current_user is not None:
        await _verify_thread_ownership(session, thread_id, current_user)

    # 构建 interrupt resume payload（传给 interrupt() 的返回值）
    resume_payload: dict = {"action": body.action}
    if body.selected_ids is not None:
        resume_payload["selected_ids"] = body.selected_ids
    if body.payload is not None:
        resume_payload.update(body.payload)
    if body.feedback is not None:
        resume_payload["feedback"] = body.feedback

    new_run_id = str(uuid.uuid4())

    # 保存 resume 快照（与 create_run 对称），避免 GET /runs/{run_id} 404
    snapshot = RunSnapshot()
    snapshot.thread_id = thread_id
    snapshot.run_id = uuid.UUID(new_run_id)
    snapshot.user_message = f"[resume] {body.action}"
    snapshot.status = "running"
    await base_repo.create(session, snapshot)
    await agent_service.update_thread_status(session, thread_id, "running")
    await session.commit()

    await runner.resume_run(
        run_id=new_run_id,
        thread_id=str(thread_id),
        resume_payload=resume_payload,
    )
    return {
        "run_id": new_run_id,
        "thread_id": str(thread_id),
        "status": "running",
        "stream_url": f"/api/v1/agent/threads/{thread_id}/runs/{new_run_id}/stream",
    }


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
    await session.commit()
