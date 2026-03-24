"""基于 Redis Pub/Sub 的 Workspace 级事件广播。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.core.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from backend.api.schemas.sse_events import SSEEvent

logger = get_logger(__name__)


class EventBroadcaster:
    """基于 Redis Pub/Sub 的 Workspace 级事件广播。

    MVP 阶段使用内存 asyncio.Queue 模拟。
    生产环境替换为 Redis Pub/Sub。
    """

    def __init__(self) -> None:
        # MVP: 内存模式 — workspace_id → list[asyncio.Queue]
        self._subscribers: dict[str, list[Any]] = {}

    async def subscribe(self, workspace_id: str) -> AsyncIterator[SSEEvent]:
        """订阅指定 Workspace 的文档事件。"""
        import asyncio

        queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        if workspace_id not in self._subscribers:
            self._subscribers[workspace_id] = []
        self._subscribers[workspace_id].append(queue)

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            self._subscribers[workspace_id].remove(queue)
            if not self._subscribers[workspace_id]:
                del self._subscribers[workspace_id]

    async def publish(self, workspace_id: str, event: SSEEvent) -> None:
        """发布事件到 Workspace 通道。"""
        queues = self._subscribers.get(workspace_id, [])
        for queue in queues:
            await queue.put(event)
        logger.info(
            "event_broadcast",
            workspace_id=workspace_id,
            event_type=event.event_type,
            subscriber_count=len(queues),
        )

    async def unsubscribe_all(self, workspace_id: str) -> None:
        """关闭指定 Workspace 的所有订阅。"""
        queues = self._subscribers.pop(workspace_id, [])
        for queue in queues:
            await queue.put(None)
