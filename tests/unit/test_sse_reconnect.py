"""SSE reconnect — TDD tests for SSEEventStore."""

import json
from unittest.mock import AsyncMock

from backend.services.sse_event_store import SSEEventStore


class TestSSEEventStore:
    """Test SSEEventStore append, get_since, and cleanup."""

    async def test_append_stores_event(self) -> None:
        redis = AsyncMock()
        store = SSEEventStore(redis)

        await store.append("run-1", 1, {"event": "status", "data": "running"})
        redis.rpush.assert_awaited_once()
        call_args = redis.rpush.call_args
        key = call_args[0][0]
        payload = json.loads(call_args[0][1])
        assert key == "sse:events:run-1"
        assert payload["seq"] == 1
        assert payload["event"] == "status"

    async def test_get_since_filters_by_seq(self) -> None:
        redis = AsyncMock()
        events = [
            json.dumps({"seq": 1, "event": "a"}),
            json.dumps({"seq": 2, "event": "b"}),
            json.dumps({"seq": 3, "event": "c"}),
        ]
        redis.lrange = AsyncMock(return_value=events)
        store = SSEEventStore(redis)

        result = await store.get_since("run-1", last_seq=1)
        assert len(result) == 2
        assert result[0]["seq"] == 2
        assert result[1]["seq"] == 3

    async def test_get_since_returns_empty_when_no_new_events(self) -> None:
        redis = AsyncMock()
        events = [json.dumps({"seq": 1, "event": "a"})]
        redis.lrange = AsyncMock(return_value=events)
        store = SSEEventStore(redis)

        result = await store.get_since("run-1", last_seq=5)
        assert result == []

    async def test_cleanup_sets_ttl(self) -> None:
        redis = AsyncMock()
        store = SSEEventStore(redis)

        await store.cleanup("run-1", ttl=1800)
        redis.expire.assert_awaited_once_with("sse:events:run-1", 1800)

    async def test_noop_when_redis_none(self) -> None:
        store = SSEEventStore(redis=None)

        # All operations should be no-ops, not raise
        await store.append("run-1", 1, {"event": "test"})
        result = await store.get_since("run-1", last_seq=0)
        assert result == []
        await store.cleanup("run-1")

    async def test_append_swallows_redis_error(self) -> None:
        redis = AsyncMock()
        redis.rpush = AsyncMock(side_effect=ConnectionError("redis down"))
        store = SSEEventStore(redis)

        # Should not raise
        await store.append("run-1", 1, {"event": "test"})

    async def test_get_since_returns_empty_on_redis_error(self) -> None:
        redis = AsyncMock()
        redis.lrange = AsyncMock(side_effect=ConnectionError("redis down"))
        store = SSEEventStore(redis)

        result = await store.get_since("run-1", last_seq=0)
        assert result == []
