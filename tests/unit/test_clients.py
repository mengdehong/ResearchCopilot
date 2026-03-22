"""Client layer tests — LangGraphRunner, StorageClient, AuthClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import jwt

from backend.clients.auth_client import AuthClient
from backend.clients.langgraph_runner import LangGraphRunner
from backend.clients.storage_client import StorageClient


def _make_mock_graph(*, has_interrupt: bool = False) -> MagicMock:
    """Create a mock CompiledStateGraph that yields test events.

    Args:
        has_interrupt: 若 True, aget_state 返回 pending next 节点（模拟 interrupt）。
    """
    graph = MagicMock()

    async def fake_astream_events(input_data, *, config=None, version="v2"):
        yield {"event": "events/metadata", "data": {"run_id": "r1"}}
        yield {"event": "events/on_chat_model_stream", "data": {"chunk": "Hi"}}

    graph.astream_events = fake_astream_events

    # Mock aget_state for interrupt detection
    state_snapshot = MagicMock()
    if has_interrupt:
        state_snapshot.next = ("present_candidates",)
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"action": "select_papers", "candidates": []}
        task_obj = MagicMock()
        task_obj.interrupts = (interrupt_obj,)
        state_snapshot.tasks = (task_obj,)
    else:
        state_snapshot.next = ()
        state_snapshot.tasks = ()

    graph.aget_state = AsyncMock(return_value=state_snapshot)

    return graph


class TestLangGraphRunner:
    async def test_start_run_and_stream(self) -> None:
        graph = _make_mock_graph()
        runner = LangGraphRunner(graph)

        await runner.start_run(run_id="r1", thread_id="t1", input_data={"messages": []})
        events = [e async for e in runner.get_event_stream("r1")]
        assert len(events) == 2
        assert events[0]["event"] == "events/metadata"

    async def test_interrupt_detection(self) -> None:
        """当图被 interrupt 暂停，_execute 应注入 __interrupt__ 事件。"""
        graph = _make_mock_graph(has_interrupt=True)
        runner = LangGraphRunner(graph)

        await runner.start_run(run_id="r1", thread_id="t1", input_data={})
        events = [e async for e in runner.get_event_stream("r1")]
        # 2 个原始事件 + 1 个 __interrupt__
        assert len(events) == 3
        interrupt_event = events[-1]
        assert interrupt_event["event"] == "__interrupt__"
        assert interrupt_event["data"]["action"] == "select_papers"
        assert interrupt_event["data"]["run_id"] == "r1"
        assert interrupt_event["data"]["thread_id"] == "t1"

    async def test_no_interrupt_when_graph_completes(self) -> None:
        """正常完成时不应生成 __interrupt__ 事件。"""
        graph = _make_mock_graph(has_interrupt=False)
        runner = LangGraphRunner(graph)

        await runner.start_run(run_id="r1", thread_id="t1", input_data={})
        events = [e async for e in runner.get_event_stream("r1")]
        assert len(events) == 2
        assert all(e["event"] != "__interrupt__" for e in events)

    async def test_cancel_run(self) -> None:
        graph = MagicMock()

        async def slow_stream(input_data, *, config=None, version="v2"):
            await asyncio.sleep(10)
            yield {"event": "events/metadata", "data": {}}

        graph.astream_events = slow_stream
        runner = LangGraphRunner(graph)

        await runner.start_run(run_id="r1", thread_id="t1", input_data={})
        await runner.cancel_run("r1")
        # After cancel, run should be removed
        assert "r1" not in runner._active_runs

    async def test_stream_unknown_run(self) -> None:
        graph = _make_mock_graph()
        runner = LangGraphRunner(graph)
        events = [e async for e in runner.get_event_stream("nonexistent")]
        assert events == []

    async def test_resume_run(self) -> None:
        """resume_run 应启动新的事件流。"""
        graph = _make_mock_graph()
        runner = LangGraphRunner(graph)

        await runner.resume_run(
            run_id="r2",
            thread_id="t1",
            resume_payload={"selected_ids": ["p1"]},
        )
        events = [e async for e in runner.get_event_stream("r2")]
        assert len(events) == 2  # 2 个原始事件（无 interrupt）

    async def test_config_includes_thread_id(self) -> None:
        """start_run 应自动在 config 中注入 thread_id。"""
        graph = _make_mock_graph()
        runner = LangGraphRunner(graph)

        await runner.start_run(run_id="r1", thread_id="t1", input_data={})
        # 等待事件消费完毕
        _ = [e async for e in runner.get_event_stream("r1")]
        # 验证 aget_state 被调用时的 config 包含 thread_id
        call_args = graph.aget_state.call_args
        config = call_args[0][0]
        assert config["configurable"]["thread_id"] == "t1"

    async def test_shutdown_cancels_all_runs(self) -> None:
        """shutdown() 应取消所有活跃 run 并清空 _active_runs。"""
        graph = MagicMock()

        async def slow_stream(input_data, *, config=None, version="v2"):
            await asyncio.sleep(60)
            yield {"event": "events/metadata", "data": {}}

        graph.astream_events = slow_stream
        runner = LangGraphRunner(graph)

        await runner.start_run(run_id="r1", thread_id="t1", input_data={})
        await runner.start_run(run_id="r2", thread_id="t2", input_data={})
        assert len(runner._active_runs) == 2

        await runner.shutdown()

        assert len(runner._active_runs) == 0

    async def test_shutdown_event_is_set(self) -> None:
        """shutdown() 後 _shutdown_event 必須設置，以便通知 SSE 消費者。"""
        graph = _make_mock_graph()
        runner = LangGraphRunner(graph)

        assert not runner._shutdown_event.is_set()
        await runner.shutdown()
        assert runner._shutdown_event.is_set()


class TestStorageClient:
    async def test_generate_upload_url(self, tmp_path) -> None:
        client = StorageClient(base_dir=str(tmp_path))
        url = await client.generate_upload_url("doc.pdf", "application/pdf")
        assert "doc.pdf" in url
        assert "expires=" in url

    async def test_head_object_missing(self, tmp_path) -> None:
        client = StorageClient(base_dir=str(tmp_path))
        assert await client.head_object("nonexistent.pdf") is False

    async def test_head_object_exists(self, tmp_path) -> None:
        client = StorageClient(base_dir=str(tmp_path))
        (tmp_path / "test.pdf").write_text("data")
        assert await client.head_object("test.pdf") is True

    async def test_delete_object(self, tmp_path) -> None:
        client = StorageClient(base_dir=str(tmp_path))
        (tmp_path / "test.pdf").write_text("data")
        await client.delete_object("test.pdf")
        assert not (tmp_path / "test.pdf").exists()


class TestAuthClient:
    async def test_verify_token(self) -> None:
        token = jwt.encode(
            {"sub": "user-1", "exp": 9999999999, "email": "a@b.com"},
            "secret",
            algorithm="HS256",
        )
        client = AuthClient()
        payload = await client.verify_token(token)
        assert payload.sub == "user-1"
        assert payload.email == "a@b.com"

    async def test_get_user_info(self) -> None:
        client = AuthClient()
        info = await client.get_user_info("ext-123")
        assert info.external_id == "ext-123"
        assert "mock.local" in info.email
