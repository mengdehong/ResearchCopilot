"""数据库连接集成测试(需要运行中的 PostgreSQL)。"""
import pytest
from sqlalchemy import text

from backend.core.database import create_engine, create_session_factory

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/research_copilot"


@pytest.fixture
async def session():
    engine = create_engine(DATABASE_URL)
    factory = create_session_factory(engine)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.integration
async def test_connection(session) -> None:
    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.integration
async def test_pgvector_extension(session) -> None:
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    result = await session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    )
    assert result.scalar() == "vector"
