"""LangGraph In-Process Runner — 在 BFF 进程内执行 LangGraph 图。

替代 Mock 的 LangGraphClient。通过 asyncio.Task + asyncio.Queue
解耦图执行和 SSE 事件消费。支持 HITL interrupt/resume。
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langgraph.types import Command

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

    Attributes:
        _shutdown_event: 应用退出时设置，供 SSE event_generator 检测并主动终止。
    """

    def __init__(self, graph: CompiledStateGraph) -> None:
        self._graph = graph
        self._active_runs: dict[str, RunHandle] = {}
        self._shutdown_event: asyncio.Event = asyncio.Event()

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
        # 确保 config 包含 thread_id（checkpointer 需要）
        configurable = run_config.setdefault("configurable", {})
        configurable.setdefault("thread_id", thread_id)

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

    async def resume_run(
        self,
        *,
        run_id: str,
        thread_id: str,
        resume_payload: dict,
    ) -> None:
        """恢复被 interrupt 暂停的 run。

        使用 Command(resume=payload) 恢复图执行，启动新的事件流。

        Args:
            run_id: 新 run 的唯一标识。
            thread_id: 所属 thread。
            resume_payload: HITL 响应（传给 interrupt 的返回值）。
        """
        if run_id in self._active_runs:
            logger.warning("run_already_active", run_id=run_id)
            return

        queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=256)
        config = {"configurable": {"thread_id": thread_id}}

        task = asyncio.create_task(
            self._execute(
                run_id=run_id,
                input_data=Command(resume=resume_payload),
                queue=queue,
                config=config,
            ),
            name=f"lg-resume-{run_id}",
        )

        self._active_runs[run_id] = RunHandle(
            task=task,
            queue=queue,
            thread_id=thread_id,
        )
        logger.info("run_resumed", run_id=run_id, thread_id=thread_id)

    async def get_event_stream(self, run_id: str) -> AsyncIterator[dict]:
        """从指定 run 的 Queue 消费事件。

        Yields LangGraph 原始事件 dict 直到 run 结束（收到 sentinel）
        或应用 shutdown（_shutdown_event 被设置）。
        """
        handle = self._active_runs.get(run_id)
        if handle is None:
            logger.warning("run_not_found_for_stream", run_id=run_id)
            return

        while True:
            # Race: 下一个队列事件 vs 应用 shutdown
            queue_task: asyncio.Task[dict | None] = asyncio.create_task(handle.queue.get())
            shutdown_task: asyncio.Task[bool] = asyncio.create_task(self._shutdown_event.wait())

            done, pending = await asyncio.wait(
                {queue_task, shutdown_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 清理未完成的任务，避免资源泄漏
            for t in pending:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t  # type: ignore[misc]

            if shutdown_task in done:
                # 应用正在退出 — 提前终止流，finally 块负责发送 run_end
                logger.info("sse_stream_aborted_on_shutdown", run_id=run_id)
                break

            # queue_task 先完成
            event = queue_task.result()
            if event is _SENTINEL:
                break
            yield event

        # Run 消费完毕，清理
        self._active_runs.pop(run_id, None)

    async def cancel_run(self, run_id: str) -> None:
        """取消活跃 run，等待 task 真正结束。"""
        handle = self._active_runs.pop(run_id, None)
        if handle is None:
            return
        handle.task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.shield(handle.task)
        logger.info("run_cancelled", run_id=run_id)

    async def shutdown(self) -> None:
        """关闭所有活跃 run（应用退出时调用）。

        1. 设置 _shutdown_event 通知所有 SSE 消费者主动退出。
        2. 并发 cancel 所有活跃 task 并等待其真正结束。
        """
        self._shutdown_event.set()
        run_ids = list(self._active_runs)
        if run_ids:
            await asyncio.gather(
                *(self.cancel_run(rid) for rid in run_ids),
                return_exceptions=True,
            )
        logger.info("langgraph_runner_shutdown", cancelled_runs=len(run_ids))

    async def _execute(
        self,
        *,
        run_id: str,
        input_data: dict | Command,
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

            # 检查是否因 interrupt 而停止
            state_snapshot = await self._graph.aget_state(config)
            if state_snapshot.next:
                # 图被 interrupt 暂停，从 tasks 中提取 interrupt payload
                interrupt_payload = self._extract_interrupt_payload(state_snapshot)
                thread_id = config.get("configurable", {}).get("thread_id", "")
                await queue.put(
                    {
                        "event": "__interrupt__",
                        "data": {
                            "run_id": run_id,
                            "thread_id": thread_id,
                            **interrupt_payload,
                        },
                    }
                )
                logger.info(
                    "interrupt_detected",
                    run_id=run_id,
                    pending_nodes=list(state_snapshot.next),
                )

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

    @staticmethod
    def _extract_interrupt_payload(state_snapshot: object) -> dict:
        """从 LangGraph state snapshot 提取 interrupt payload。

        state_snapshot.tasks 是包含 interrupts 的 PregelTask 列表。
        每个 task.interrupts 是 Interrupt 对象列表，每个有 .value 属性。
        """
        tasks = getattr(state_snapshot, "tasks", ())
        for task in tasks:
            interrupts = getattr(task, "interrupts", ())
            for intr in interrupts:
                value = getattr(intr, "value", None)
                if isinstance(value, dict):
                    return value
        return {}
