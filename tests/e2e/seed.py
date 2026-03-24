"""E2E 测试种子数据 — 通过 API + 直接 DB 写入创建。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True)
class SeedData:
    """Session 级种子数据，所有测试共享。"""

    # User A (主测试用户)
    user_id: uuid.UUID
    user_email: str
    access_token: str

    # User B (权限隔离用)
    user_b_id: uuid.UUID
    user_b_email: str
    user_b_access_token: str

    # Workspace (User A) — 通过 API 创建后填充
    workspace_id: uuid.UUID

    # Workspace (User B) — 通过 API 创建后填充
    workspace_b_id: uuid.UUID


def sign_test_token(user_id: uuid.UUID, secret: str, algorithm: str) -> str:
    """为测试用户签发 JWT access token。"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)
