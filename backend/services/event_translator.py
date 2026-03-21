"""SSE event translator — 将 LangGraph 内部事件翻译为 SSEEvent 信封格式。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.api.schemas.sse_events import SSEEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# LangGraph astream_events v2 → SSE 事件类型映射
_EVENT_MAPPING: dict[str, str] = {
    # v2 事件类型（无 events/ 前缀）
    "on_chain_start": "node_enter",
    "on_chain_end": "node_exit",
    "on_chat_model_start": "node_enter",
    "on_chat_model_stream": "token_delta",
    "on_chat_model_end": "node_exit",
    "on_tool_start": "node_enter",
    "on_tool_end": "node_exit",
    # 兼容旧 events/ 前缀（Mock / LangGraph Platform）
    "events/metadata": "run_start",
    "events/on_chain_start": "node_enter",
    "events/on_chain_end": "node_exit",
    "events/on_chat_model_stream": "token_delta",
    "events/on_tool_start": "node_enter",
    "events/on_tool_end": "node_exit",
    "events/updates": "content_generated",
    "events/error": "run_error",
    "__interrupt__": "interrupt",
}

# 兼容旧映射（保留给已存在测试）
EVENT_MAPPING: dict[str, str] = {
    "on_chain_start": "chain_start",
    "on_chain_end": "chain_end",
    "on_chat_model_start": "chain_start",
    "on_chat_model_stream": "token",
    "on_chat_model_end": "chain_end",
    "on_tool_start": "tool_start",
    "on_tool_end": "tool_end",
    # 兼容旧 events/ 前缀
    "events/metadata": "metadata",
    "events/on_chain_start": "chain_start",
    "events/on_chain_end": "chain_end",
    "events/on_chat_model_stream": "token",
    "events/on_tool_start": "tool_start",
    "events/on_tool_end": "tool_end",
    "events/updates": "state_update",
    "events/error": "error",
    "__interrupt__": "interrupt",
}


def translate_event(raw_event: dict) -> dict | None:
    """将单个 LangGraph 事件翻译为前端格式（兼容旧接口）。

    Returns None if the event type is unknown (should be silently dropped).
    """
    raw_type = raw_event.get("event", "")
    frontend_type = EVENT_MAPPING.get(raw_type)
    if frontend_type is None:
        return None

    return {
        "event": frontend_type,
        "data": raw_event.get("data", {}),
    }


def translate_to_sse_event(raw_event: dict, *, seq: int) -> SSEEvent | None:
    """将单个 LangGraph 事件翻译为 SSEEvent 信封格式。

    Returns None if the event type is unknown.
    """
    raw_type = raw_event.get("event", "")
    event_type = _EVENT_MAPPING.get(raw_type)
    if event_type is None:
        return None

    data = raw_event.get("data", {})
    payload: dict = {}

    match event_type:
        case "run_start":
            payload = {
                "run_id": data.get("run_id", ""),
                "thread_id": data.get("thread_id", ""),
                "workflow": data.get("workflow"),
            }
        case "node_enter":
            payload = {
                "node_id": data.get("run_id", str(uuid.uuid4())),
                "node_name": data.get("name", raw_type),
                "parent_node_id": data.get("parent_run_id"),
            }
        case "node_exit":
            payload = {
                "node_id": data.get("run_id", ""),
                "node_name": data.get("name", raw_type),
                "status": "completed",
                "duration_ms": 0,
            }
        case "token_delta":
            chunk = data.get("chunk", "")
            if hasattr(chunk, "content"):
                chunk = chunk.content
            payload = {
                "node_name": data.get("name", ""),
                "delta": str(chunk),
                "role": "assistant",
            }
        case "content_generated":
            payload = {
                "content_type": "markdown",
                "content": str(data),
                "target_tab": "editor",
            }
        case "run_error":
            payload = {
                "run_id": data.get("run_id", ""),
                "error_type": "internal",
                "message": str(data.get("error", "")),
                "duration_ms": 0,
            }
        case "interrupt":
            payload = {
                "interrupt_type": data.get("action", "confirm_execute"),
                "title": data.get("title", "Human Review Required"),
                "description": data.get("description", ""),
                "data": data,
            }

    return SSEEvent(
        seq=seq,
        event_type=event_type,
        timestamp=datetime.now(UTC).isoformat(),
        payload=payload,
    )


async def translate_stream(
    raw_stream: AsyncIterator[dict],
) -> AsyncIterator[dict]:
    """翻译完整 LangGraph 事件流（兼容旧接口），丢弃未知事件。"""
    async for raw_event in raw_stream:
        translated = translate_event(raw_event)
        if translated is not None:
            yield translated


async def translate_sse_stream(
    raw_stream: AsyncIterator[dict],
) -> AsyncIterator[SSEEvent]:
    """翻译 LangGraph 事件流为 SSEEvent 信封流。"""
    seq = 0
    async for raw_event in raw_stream:
        translated = translate_to_sse_event(raw_event, seq=seq + 1)
        if translated is not None:
            seq += 1
            yield translated
