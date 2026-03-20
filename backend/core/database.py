"""PostgreSQL 异步数据库引擎、Session 工厂与 LangGraph checkpointer 支点。"""
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """创建 SQLAlchemy 异步引擎。"""
    return create_async_engine(
        database_url, echo=echo, pool_size=20, max_overflow=10, pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建 Session 工厂。"""
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """每请求一个 session, 请求结束自动关闭。"""
    async with session_factory() as session:
        yield session


def normalize_postgres_dsn_for_langgraph(database_url: str) -> str:
    """将 SQLAlchemy asyncpg DSN 规范化为 LangGraph 可用 DSN。"""
    url = make_url(database_url)
    if url.drivername == "postgresql+asyncpg":
        return url.set(drivername="postgresql").render_as_string(hide_password=False)
    if url.drivername == "postgresql":
        return url.render_as_string(hide_password=False)
    raise ValueError(f"Unsupported PostgreSQL driver for LangGraph checkpointer: {url.drivername}")


def _load_async_postgres_saver() -> type["AsyncPostgresSaver"]:
    """延迟导入 LangGraph PostgresSaver, 避免在纯 DB 场景引入硬依赖。"""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    return AsyncPostgresSaver


@asynccontextmanager
async def create_checkpointer(database_url: str) -> AsyncIterator["AsyncPostgresSaver"]:
    """创建可供 LangGraph compile 使用的 Postgres checkpointer。"""
    checkpointer_dsn = normalize_postgres_dsn_for_langgraph(database_url)
    async_postgres_saver = _load_async_postgres_saver()
    async with async_postgres_saver.from_conn_string(checkpointer_dsn) as saver:
        yield saver


async def setup_checkpointer(database_url: str) -> None:
    """初始化 LangGraph checkpoint schema。"""
    async with create_checkpointer(database_url) as saver:
        await saver.setup()
