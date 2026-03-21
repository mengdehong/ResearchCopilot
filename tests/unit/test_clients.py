"""Client layer tests — LangGraphRunner, StorageClient, AuthClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import jwt

from backend.clients.auth_client import AuthClient
from backend.clients.langgraph_runner import LangGraphRunner
from backend.clients.storage_client import StorageClient


def _make_mock_graph() -> MagicMock:
    """Create a mock CompiledStateGraph that yields test events."""
    graph = MagicMock()

    async def fake_astream_events(input_data, *, config=None, version="v2"):
        yield {"event": "events/metadata", "data": {"run_id": "r1"}}
        yield {"event": "events/on_chat_model_stream", "data": {"chunk": "Hi"}}

    graph.astream_events = fake_astream_events
    return graph


class TestLangGraphRunner:
    async def test_start_run_and_stream(self) -> None:
        graph = _make_mock_graph()
        runner = LangGraphRunner(graph)

        await runner.start_run(run_id="r1", thread_id="t1", input_data={"messages": []})
        events = [e async for e in runner.get_event_stream("r1")]
        assert len(events) == 2
        assert events[0]["event"] == "events/metadata"

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
