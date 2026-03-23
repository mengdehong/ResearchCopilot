"""SSE event translator — 将 LangGraph 内部事件翻译为前端 RunEvent 格式。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.core.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


def _extract_chunk_text(chunk: object) -> str:
    """从 LangGraph on_chat_model_stream 的 chunk 中提取纯文本。

    chunk 可能是:
    - AIMessageChunk 对象（.content 为 str 或 list[dict]）
    - list[dict]（Gemini 格式：[{"type":"text","text":"..."}]）
    - str（直接文本）
    """
    # AIMessageChunk → 取 .content
    if hasattr(chunk, "content"):
        chunk = chunk.content

    # str → 直接返回
    if isinstance(chunk, str):
        return chunk

    # list[dict] → 拼接所有 text 块
    if isinstance(chunk, list):
        parts: list[str] = []
        for block in chunk:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)

    return str(chunk)


# 内部节点：这些节点的 on_chat_model_stream 事件不应转发给前端
# （它们使用 structured_output 做路由/评估，输出的是 JSON 而非自然语言）
_INTERNAL_NODES: frozenset[str] = frozenset(
    {
        "supervisor",
        "checkpoint_eval",
    }
)


# LangGraph astream_events v2 → 前端 event_type 映射
# 前端 RunEvent 类型: token | node_start | node_end | interrupt | assistant_message | run_end
#
# 注意：当前所有 LLM 调用都使用 with_structured_output().invoke()，
# 产出的是内部 JSON（路由决策/结构化结果），不是面向用户的自然语言。
# 因此 on_chat_model_stream/start/end 不映射——它们只会泄露内部 JSON。
# 当未来增加面向用户的流式文本生成时，需针对那些 LLM 调用添加映射。
_EVENT_MAPPING: dict[str, str] = {
    # 图节点的生命周期（结合 graph:step tag 过滤，只转发顶层节点）
    "on_chain_start": "node_start",
    "on_chain_end": "node_end",
    # on_chat_model_* 事件: 全部排除（见上方说明）
    # on_tool_* 事件：如果将来添加 tool 调用可在此开启
    "on_tool_start": "node_start",
    "on_tool_end": "node_end",
    # 兼容旧 events/ 前缀（Mock / LangGraph Platform）
    "events/on_chain_start": "node_start",
    "events/on_chain_end": "node_end",
    "events/on_tool_start": "node_start",
    "events/on_tool_end": "node_end",
    "events/error": "error",
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


def translate_to_run_event(raw_event: dict) -> dict | None:
    """将单个 LangGraph 事件翻译为前端 RunEvent 格式。

    输出格式: { event_type: str, data: { ... } }
    与前端 RunEvent 类型完全对齐。
    Returns None if the event type is unknown or should be filtered.
    """
    raw_type = raw_event.get("event", "")
    event_type = _EVENT_MAPPING.get(raw_type)
    if event_type is None:
        return None

    # ── 过滤内部事件 ──
    metadata = raw_event.get("metadata", {})
    source_node = metadata.get("langgraph_node", "")

    # token 事件：只转发来自工作流节点的（排除 supervisor/checkpoint_eval 的结构化输出）
    if event_type == "token" and source_node in _INTERNAL_NODES:
        return None

    # node_start/end 事件：只转发有 langgraph_node 的（即实际图节点，而非内部 chain wrapper）
    if event_type in ("node_start", "node_end") and not source_node:
        return None

    raw_data = raw_event.get("data", {})
    data: dict = {}

    match event_type:
        case "token":
            chunk = raw_data.get("chunk", "")
            content = _extract_chunk_text(chunk)
            data = {"content": content}
        case "node_start":
            node_name = raw_data.get("name", "") or raw_event.get("name", raw_type)
            data = {
                "node_name": node_name,
                "node_id": raw_data.get("run_id", ""),
            }
        case "node_end":
            node_name = raw_data.get("name", "") or raw_event.get("name", raw_type)
            data = {
                "node_name": node_name,
                "node_id": raw_data.get("run_id", ""),
            }
        case "interrupt":
            data = {
                "action": raw_data.get("action", "confirm_execute"),
                "run_id": raw_data.get("run_id", ""),
                "thread_id": raw_data.get("thread_id", ""),
                "title": raw_data.get("title", "Human Review Required"),
                "description": raw_data.get("description", ""),
                "papers": raw_data.get("candidates", []),
                # 保留 action 对应的 payload 字段
                "code": raw_data.get("code"),
                "content": raw_data.get("content"),
            }
        case "error":
            data = {
                "message": str(raw_data.get("error", "")),
                "run_id": raw_data.get("run_id", ""),
            }

    return {"event_type": event_type, "data": data}


async def translate_stream(
    raw_stream: AsyncIterator[dict],
) -> AsyncIterator[dict]:
    """翻译完整 LangGraph 事件流（兼容旧接口），丢弃未知事件。"""
    async for raw_event in raw_stream:
        translated = translate_event(raw_event)
        if translated is not None:
            yield translated


async def translate_run_event_stream(
    raw_stream: AsyncIterator[dict],
) -> AsyncIterator[dict]:
    """翻译 LangGraph 事件流为前端 RunEvent 格式。

    输出 { event_type, data } dict，与前端 RunEvent 接口一致。
    """
    raw_count = 0
    translated_count = 0
    async for raw_event in raw_stream:
        raw_count += 1
        raw_type = raw_event.get("event", "<missing>")
        translated = translate_to_run_event(raw_event)
        if translated is not None:
            translated_count += 1
            yield translated
        else:
            logger.debug(
                "sse_event_dropped",
                raw_type=raw_type,
                raw_name=raw_event.get("name", ""),
            )
    logger.info(
        "translate_stream_done",
        raw_count=raw_count,
        translated_count=translated_count,
    )
