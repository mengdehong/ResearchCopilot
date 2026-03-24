"""SSE event store — Redis-backed event persistence for reconnection replay.

Stores SSE events per run_id in Redis Lists with TTL, enabling
Last-Event-ID based reconnection and message replay.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from backend.core.logger import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)

_KEY_PREFIX = "sse:events:"
_DEFAULT_TTL_SECONDS = 3600  # 1 hour


class SSEEventStore:
    """Redis-backed SSE event store for reconnection replay.

    Each run's events are stored in a Redis List keyed by run_id.
    Events are JSON-encoded dicts with mandatory 'seq' field.

    Degrades gracefully when Redis is unavailable — all operations
    become no-ops, which only affects reconnection (not first connect).
    """

    def __init__(self, redis: Redis | None) -> None:
        self._redis = redis

    def _key(self, run_id: str) -> str:
        return f"{_KEY_PREFIX}{run_id}"

    async def append(self, run_id: str, seq: int, event_data: dict[str, Any]) -> None:
        """Append an event to the store."""
        if self._redis is None:
            return
        try:
            payload = json.dumps({"seq": seq, **event_data})
            await self._redis.rpush(self._key(run_id), payload)
        except Exception:
            logger.warning("sse_event_store_append_failed", run_id=run_id, seq=seq)

    async def get_since(self, run_id: str, last_seq: int) -> list[dict[str, Any]]:
        """Return all events with seq > last_seq."""
        if self._redis is None:
            return []
        try:
            raw_events = await self._redis.lrange(self._key(run_id), 0, -1)
            result: list[dict[str, Any]] = []
            for raw in raw_events:
                event = json.loads(raw)
                if event.get("seq", 0) > last_seq:
                    result.append(event)
            return result
        except Exception:
            logger.warning("sse_event_store_get_since_failed", run_id=run_id)
            return []

    async def cleanup(self, run_id: str, ttl: int = _DEFAULT_TTL_SECONDS) -> None:
        """Set TTL on the event list so it auto-expires after run completion."""
        if self._redis is None:
            return
        try:
            await self._redis.expire(self._key(run_id), ttl)
        except Exception:
            logger.warning("sse_event_store_cleanup_failed", run_id=run_id)
