"""MockLangGraphRunner — 确定性返回，用于 E2E 测试。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class MockLangGraphRunner:
    """返回固定事件的 LangGraph Runner，记录调用供断言。"""

    calls: list[tuple[str, dict]] = field(default_factory=list)
    _queues: dict[str, asyncio.Queue] = field(default_factory=dict)

    async def start_run(
        self,
        *,
        run_id: str,
        thread_id: str,
        input_data: dict,
        config: dict | None = None,
    ) -> None:
        """记录调用并填充固定事件到 queue。"""
        self.calls.append(("start_run", {"run_id": run_id, "thread_id": thread_id}))
        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        events = [
            {"event": "events/on_chain_start", "data": {"name": "research_graph"}},
            {"event": "events/on_chat_model_stream", "data": {"chunk": "Hello"}},
            {"event": "events/on_chain_end", "data": {"output": "Done"}},
        ]
        for event in events:
            await queue.put(event)
        await queue.put(None)  # sentinel
        self._queues[run_id] = queue

    async def get_event_stream(self, run_id: str) -> AsyncIterator[dict]:
        """从 queue 消费事件。"""
        self.calls.append(("get_event_stream", {"run_id": run_id}))
        queue = self._queues.get(run_id)
        if queue is None:
            return
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

    async def cancel_run(self, run_id: str) -> None:
        """取消 run。"""
        self.calls.append(("cancel_run", {"run_id": run_id}))
        self._queues.pop(run_id, None)

    async def shutdown(self) -> None:
        """关闭所有 run。"""
        self._queues.clear()
