"""SSE event translator — map LangGraph events to frontend-friendly SSE format."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# Mapping from LangGraph internal event types to frontend event types.
EVENT_MAPPING: dict[str, str] = {
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
    """Translate a single LangGraph event to frontend format.

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


async def translate_stream(
    raw_stream: AsyncIterator[dict],
) -> AsyncIterator[dict]:
    """Translate a full LangGraph event stream, dropping unknown events."""
    async for raw_event in raw_stream:
        translated = translate_event(raw_event)
        if translated is not None:
            yield translated
