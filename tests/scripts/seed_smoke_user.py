"""Seed a deterministic verified local user for browser smoke tests."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.models.document import Document
from backend.models.editor_draft import EditorDraft
from backend.models.refresh_token import RefreshToken
from backend.models.run_snapshot import RunSnapshot
from backend.models.thread import Thread
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.services.auth_service import hash_password

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class SmokeSeedConfigError(RuntimeError):
    """Raised when smoke seed configuration is missing."""


@dataclass(frozen=True)
class SmokeUserConfig:
    """Deterministic credentials used by local browser smoke tests."""

    email: str
    password: str
    display_name: str


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SmokeSeedConfigError(f"Missing required smoke seed env: {name}")
    return value


def _load_smoke_user_config() -> SmokeUserConfig:
    return SmokeUserConfig(
        email=_require_env("SMOKE_TEST_EMAIL"),
        password=_require_env("SMOKE_TEST_PASSWORD"),
        display_name=_require_env("SMOKE_TEST_DISPLAY_NAME"),
    )


async def _find_user(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _list_workspace_ids(
    session: AsyncSession,
    owner_id: uuid.UUID,
) -> list[uuid.UUID]:
    result = await session.execute(select(Workspace.id).where(Workspace.owner_id == owner_id))
    return [row[0] for row in result.all()]


async def _list_thread_ids(
    session: AsyncSession,
    workspace_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    if not workspace_ids:
        return []

    result = await session.execute(select(Thread.id).where(Thread.workspace_id.in_(workspace_ids)))
    return [row[0] for row in result.all()]


async def _delete_user_children(session: AsyncSession, user_id: uuid.UUID) -> None:
    workspace_ids = await _list_workspace_ids(session, user_id)
    thread_ids = await _list_thread_ids(session, workspace_ids)

    if thread_ids:
        await session.execute(delete(EditorDraft).where(EditorDraft.thread_id.in_(thread_ids)))
        await session.execute(delete(RunSnapshot).where(RunSnapshot.thread_id.in_(thread_ids)))
        await session.execute(delete(Thread).where(Thread.id.in_(thread_ids)))

    if workspace_ids:
        await session.execute(delete(Document).where(Document.workspace_id.in_(workspace_ids)))
        await session.execute(delete(Workspace).where(Workspace.id.in_(workspace_ids)))

    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))


async def _upsert_smoke_user(session: AsyncSession, config: SmokeUserConfig) -> None:
    user = await _find_user(session, config.email)

    if user is None:
        session.add(
            User(
                external_id=f"smoke:{config.email}",
                email=config.email,
                display_name=config.display_name,
                settings={},
                password_hash=hash_password(config.password),
                email_verified=True,
                auth_provider="local",
            )
        )
        return

    await _delete_user_children(session, user.id)
    user.display_name = config.display_name
    user.password_hash = hash_password(config.password)
    user.email_verified = True
    user.auth_provider = "local"
    user.settings = {}


async def _seed_smoke_user(config: SmokeUserConfig) -> None:
    settings = Settings()
    engine = create_engine(
        settings.database_url,
        echo=False,
        pool_size=1,
        max_overflow=0,
        pool_timeout=30,
        pool_recycle=1800,
    )
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            await _upsert_smoke_user(session, config)
            await session.commit()
    finally:
        await engine.dispose()


async def main() -> None:
    config = _load_smoke_user_config()
    await _seed_smoke_user(config)
    print(f"Seeded smoke user: {config.email}")


if __name__ == "__main__":
    asyncio.run(main())
