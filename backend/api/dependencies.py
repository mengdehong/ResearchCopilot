"""FastAPI dependency injection: DB Session, JWT auth, Workspace checks."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import jwt
from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings
from backend.core.logger import get_logger
from backend.models.user import User
from backend.models.workspace import Workspace

if TYPE_CHECKING:
    from backend.clients.langgraph_runner import LangGraphRunner

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DB Session
# ---------------------------------------------------------------------------


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request, auto-close on exit.

    Reads session_factory from app.state (set during lifespan).
    """
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def get_settings(request: Request) -> Settings:
    """Read Settings from app.state."""
    return request.app.state.settings


# ---------------------------------------------------------------------------
# JWT auth
# ---------------------------------------------------------------------------


async def _resolve_user(
    raw_token: str,
    session: AsyncSession,
    settings: Settings,
) -> User:
    """Decode JWT, look up User, raise 401 on failure."""
    if raw_token.startswith("Bearer "):
        raw_token = raw_token[7:]

    try:
        payload = jwt.decode(
            raw_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID in token") from None

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_current_user(
    *,
    token: str | None = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Decode JWT Bearer token (from header) and return User from DB."""
    if token is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    return await _resolve_user(token, session, settings)


async def get_current_user_sse(
    *,
    token: str | None = Query(None),
    authorization: str | None = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve user from query param `?token=` or Authorization header.

    EventSource 无法设置 Authorization header，SSE 端点需要同时
    支持 query param 和 header 两种方式。
    """
    raw_token = authorization or (f"Bearer {token}" if token else None)
    if raw_token is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    return await _resolve_user(raw_token, session, settings)


# ---------------------------------------------------------------------------
# Workspace ownership check
# ---------------------------------------------------------------------------


async def get_workspace(
    *,
    workspace_id: uuid.UUID,
    session: AsyncSession,
    current_user: User,
) -> Workspace:
    """Query Workspace and verify ownership.

    Raises:
        HTTPException(404): workspace not found or deleted.
        HTTPException(403): user is not workspace owner.
    """
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await session.execute(stmt)
    workspace = result.scalar_one_or_none()

    if workspace is None or workspace.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    return workspace


# ---------------------------------------------------------------------------
# LangGraph Runner
# ---------------------------------------------------------------------------


def get_lg_runner(request: Request) -> LangGraphRunner:
    """Read LangGraphRunner from app.state. Raises 503 if not initialized."""
    runner: LangGraphRunner | None = getattr(request.app.state, "lg_runner", None)
    if runner is None:
        raise HTTPException(
            status_code=503,
            detail="Agent service unavailable (LLM not configured)",
        )
    return runner
