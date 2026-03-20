"""Client layer tests — LangGraphClient, StorageClient, AuthClient."""

import jwt

from backend.clients.auth_client import AuthClient
from backend.clients.langgraph_client import LangGraphClient
from backend.clients.storage_client import StorageClient


class TestLangGraphClient:
    async def test_create_thread(self) -> None:
        client = LangGraphClient()
        info = await client.create_thread(metadata={"ws": "test"})
        assert info.thread_id
        assert info.metadata == {"ws": "test"}

    async def test_create_run(self) -> None:
        client = LangGraphClient()
        info = await client.create_run(
            "thread-1",
            assistant_id="default",
            input_data={"message": "hello"},
        )
        assert info.run_id
        assert info.thread_id == "thread-1"
        assert info.status == "pending"

    async def test_stream_run(self) -> None:
        client = LangGraphClient()
        events = [e async for e in client.stream_run("t1", "r1")]
        assert len(events) >= 1
        assert events[0]["event"] == "events/metadata"

    async def test_resume_run(self) -> None:
        client = LangGraphClient()
        info = await client.resume_run("t1", command={"resume": "approve"})
        assert info.status == "resuming"

    async def test_cancel_run(self) -> None:
        client = LangGraphClient()
        await client.cancel_run("t1", "r1")  # should not raise

    async def test_get_thread_state(self) -> None:
        client = LangGraphClient()
        state = await client.get_thread_state("t1")
        assert state["thread_id"] == "t1"
        assert "values" in state


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
