"""PostgreSQL 异步数据库引擎与 Session 工厂。"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


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
