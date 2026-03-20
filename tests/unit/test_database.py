"""数据库基础设施单元测试。"""

import pytest

from backend.core import database


def test_normalize_postgres_dsn_for_langgraph() -> None:
    """应将 asyncpg DSN 规范化为 psycopg DSN。"""
    dsn = "postgresql+asyncpg://user:pass@localhost:5432/research_copilot"

    normalized = database.normalize_postgres_dsn_for_langgraph(dsn)

    assert normalized == "postgresql://user:pass@localhost:5432/research_copilot"


@pytest.mark.asyncio
async def test_setup_checkpointer_calls_async_postgres_saver_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """应创建 AsyncPostgresSaver 并执行 setup。"""
    captured: dict[str, object] = {}

    class FakeSaver:
        async def setup(self) -> None:
            captured["setup_called"] = True

    class FakeContextManager:
        async def __aenter__(self) -> FakeSaver:
            captured["entered"] = True
            return FakeSaver()

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            tb: object,
        ) -> None:
            del exc_type, exc, tb
            captured["exited"] = True

    class FakeAsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, conn_string: str) -> FakeContextManager:
            captured["conn_string"] = conn_string
            return FakeContextManager()

    monkeypatch.setattr(
        database,
        "_load_async_postgres_saver",
        lambda: FakeAsyncPostgresSaver,
    )

    await database.setup_checkpointer(
        "postgresql+asyncpg://user:pass@localhost:5432/research_copilot"
    )

    assert captured["conn_string"] == "postgresql://user:pass@localhost:5432/research_copilot"
    assert captured["entered"] is True
    assert captured["setup_called"] is True
    assert captured["exited"] is True


@pytest.mark.asyncio
async def test_checkpointer_context_manager_closes_saver(monkeypatch: pytest.MonkeyPatch) -> None:
    """context manager 退出时应关闭 saver。"""
    captured: dict[str, object] = {"closed": False}

    class FakeSaver:
        async def __aenter__(self) -> "FakeSaver":
            return self

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            tb: object,
        ) -> None:
            del exc_type, exc, tb
            captured["closed"] = True

    class FakeAsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, conn_string: str) -> FakeSaver:
            captured["conn_string"] = conn_string
            return FakeSaver()

    monkeypatch.setattr(
        database,
        "_load_async_postgres_saver",
        lambda: FakeAsyncPostgresSaver,
    )

    async with database.create_checkpointer(
        "postgresql+asyncpg://user:pass@localhost:5432/research_copilot"
    ) as saver:
        assert isinstance(saver, FakeSaver)

    assert captured["conn_string"] == "postgresql://user:pass@localhost:5432/research_copilot"
    assert captured["closed"] is True
