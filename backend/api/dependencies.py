"""FastAPI 依赖注入：DB Session、JWT 认证、Workspace 权限校验。"""  # noqa: RUF002
import uuid
from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.config import Settings
from backend.core.logger import get_logger
from backend.models.user import User
from backend.models.workspace import Workspace

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DB Session
# ---------------------------------------------------------------------------

async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """每请求一个 session, 请求结束自动关闭。

    在 Router 中通过 Depends 链从 app.state.session_factory 获取。
    """
    async with session_factory() as session:
        yield session


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """从 app.state 获取 session_factory。供 Depends 链使用。"""
    return request.app.state.session_factory


def _get_settings(request: Request) -> Settings:
    """从 app.state 获取 Settings。供 Depends 链使用。"""
    return request.app.state.settings


# ---------------------------------------------------------------------------
# JWT 认证
# ---------------------------------------------------------------------------

async def get_current_user(
    *,
    token: str | None = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(_get_session_factory),
    settings: Settings = Depends(_get_settings),
) -> User:
    """解析 JWT Bearer token, 查 DB 返回 User 实例。

    Raises:
        HTTPException(401): token 缺失、过期或用户不存在。
    """
    if token is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    # Strip "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
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


# ---------------------------------------------------------------------------
# Workspace 权限校验
# ---------------------------------------------------------------------------

async def get_workspace(
    *,
    workspace_id: uuid.UUID,
    session: AsyncSession,
    current_user: User,
) -> Workspace:
    """查询 Workspace 并校验所有权。

    Raises:
        HTTPException(404): workspace 不存在或已删除。
        HTTPException(403): 用户不是 workspace 所有者。
    """
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await session.execute(stmt)
    workspace = result.scalar_one_or_none()

    if workspace is None or workspace.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    return workspace
