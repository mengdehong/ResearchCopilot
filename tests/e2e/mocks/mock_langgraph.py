"""MockLangGraphClient — 确定性返回，用于 E2E 测试。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from backend.clients.langgraph_client import RunInfo, ThreadInfo


@dataclass
class MockLangGraphClient:
    """返回固定结果的 LangGraph 客户端，记录调用供断言。"""

    calls: list[tuple[str, dict]] = field(default_factory=list)

    async def create_thread(self, *, metadata: dict[str, str] | None = None) -> ThreadInfo:
        """创建 thread，返回固定 ID。"""
        self.calls.append(("create_thread", {"metadata": metadata}))
        return ThreadInfo(
            thread_id=str(uuid.uuid4()),
            metadata=metadata or {},
        )

    async def create_run(
        self,
        thread_id: str,
        *,
        assistant_id: str,
        input_data: dict,
        config: dict | None = None,
    ) -> RunInfo:
        """提交 run，返回固定结果。"""
        self.calls.append(
            (
                "create_run",
                {
                    "thread_id": thread_id,
                    "assistant_id": assistant_id,
                    "input_data": input_data,
                },
            )
        )
        return RunInfo(
            run_id=str(uuid.uuid4()),
            thread_id=thread_id,
            status="pending",
        )

    async def stream_run(self, thread_id: str, run_id: str) -> AsyncIterator[dict]:
        """生成 3 个固定 SSE 事件。"""
        self.calls.append(("stream_run", {"thread_id": thread_id, "run_id": run_id}))
        events = [
            {"event": "on_chain_start", "data": {"name": "research_graph"}},
            {"event": "on_chat_model_stream", "data": {"chunk": "Hello"}},
            {"event": "on_chain_end", "data": {"output": "Done"}},
        ]
        for event in events:
            yield event

    async def resume_run(self, thread_id: str, *, command: dict) -> RunInfo:
        """恢复暂停的 run。"""
        self.calls.append(("resume_run", {"thread_id": thread_id, "command": command}))
        return RunInfo(
            run_id=str(uuid.uuid4()),
            thread_id=thread_id,
            status="resuming",
        )

    async def cancel_run(self, thread_id: str, run_id: str) -> None:
        """取消 run。"""
        self.calls.append(("cancel_run", {"thread_id": thread_id, "run_id": run_id}))

    async def get_thread_state(self, thread_id: str) -> dict:
        """获取 thread 状态快照。"""
        self.calls.append(("get_thread_state", {"thread_id": thread_id}))
        return {"thread_id": thread_id, "values": {}, "next": []}
