"""LangGraph In-Process Runner — 在 BFF 进程内执行 LangGraph 图。

替代 Mock 的 LangGraphClient。通过 asyncio.Task + asyncio.Queue
解耦图执行和 SSE 事件消费。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.core.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langgraph.graph.state import CompiledStateGraph

logger = get_logger(__name__)

# Queue 中的 sentinel 值，表示 run 结束
_SENTINEL: None = None


@dataclass
class RunHandle:
    """活跃 run 的句柄。"""

    task: asyncio.Task[None]
    queue: asyncio.Queue[dict | None]
    thread_id: str


class LangGraphRunner:
    """在 FastAPI 进程内执行 LangGraph 编译图。

    每次 start_run 启动一个 asyncio.Task，通过 astream_events
    将事件写入 per-run 的 asyncio.Queue，SSE 端点从 Queue 消费。
    """

    def __init__(self, graph: CompiledStateGraph) -> None:
        self._graph = graph
        self._active_runs: dict[str, RunHandle] = {}

    async def start_run(
        self,
        *,
        run_id: str,
        thread_id: str,
        input_data: dict,
        config: dict | None = None,
    ) -> None:
        """启动图执行。事件通过 get_event_stream 消费。

        Args:
            run_id: 唯一 run 标识。
            thread_id: 所属 thread。
            input_data: 图的初始输入（SharedState 字段）。
            config: 可选的 LangGraph config（tags, metadata 等）。
        """
        if run_id in self._active_runs:
            logger.warning("run_already_active", run_id=run_id)
            return

        queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=256)
        run_config = config or {}

        task = asyncio.create_task(
            self._execute(run_id=run_id, input_data=input_data, queue=queue, config=run_config),
            name=f"lg-run-{run_id}",
        )

        self._active_runs[run_id] = RunHandle(
            task=task,
            queue=queue,
            thread_id=thread_id,
        )
        logger.info("run_started", run_id=run_id, thread_id=thread_id)

    async def get_event_stream(self, run_id: str) -> AsyncIterator[dict]:
        """从指定 run 的 Queue 消费事件。

        Yields LangGraph 原始事件 dict 直到 run 结束（收到 sentinel）。
        """
        handle = self._active_runs.get(run_id)
        if handle is None:
            logger.warning("run_not_found_for_stream", run_id=run_id)
            return

        while True:
            event = await handle.queue.get()
            if event is _SENTINEL:
                break
            yield event

        # Run 消费完毕，清理
        self._active_runs.pop(run_id, None)

    async def cancel_run(self, run_id: str) -> None:
        """取消活跃 run。"""
        handle = self._active_runs.pop(run_id, None)
        if handle is None:
            return
        handle.task.cancel()
        logger.info("run_cancelled", run_id=run_id)

    async def shutdown(self) -> None:
        """关闭所有活跃 run（应用退出时调用）。"""
        for run_id in list(self._active_runs):
            await self.cancel_run(run_id)

    async def _execute(
        self,
        *,
        run_id: str,
        input_data: dict,
        queue: asyncio.Queue[dict | None],
        config: dict,
    ) -> None:
        """实际执行图并将事件写入 Queue。"""
        try:
            async for event in self._graph.astream_events(
                input_data,
                config=config,
                version="v2",
            ):
                await queue.put(event)
        except asyncio.CancelledError:
            logger.info("run_cancelled_during_execution", run_id=run_id)
        except Exception:
            logger.exception("run_execution_error", run_id=run_id)
            await queue.put(
                {
                    "event": "events/error",
                    "data": {"run_id": run_id, "error": "Internal execution error"},
                }
            )
        finally:
            # 发送 sentinel 表示流结束
            await queue.put(_SENTINEL)
