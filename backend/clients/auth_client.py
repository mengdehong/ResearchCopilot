"""Third-party auth client — mock implementation for MVP."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT token payload."""

    sub: str
    exp: int
    email: str | None = None


@dataclass(frozen=True)
class AuthUserInfo:
    """User info from third-party auth provider."""

    external_id: str
    email: str
    display_name: str


class AuthClient:
    """Third-party Auth JWT verification.

    MVP: accepts any well-formed JWT and returns mock user info.
    Phase 8: replace with real auth provider SDK.
    """

    async def verify_token(self, token: str) -> TokenPayload:
        """Verify JWT token and return decoded payload.

        MVP: no real verification — trusts the token.
        """
        import jwt

        payload = jwt.decode(token, options={"verify_signature": False})
        return TokenPayload(
            sub=payload.get("sub", str(uuid.uuid4())),
            exp=payload.get("exp", 0),
            email=payload.get("email"),
        )

    async def get_user_info(self, external_id: str) -> AuthUserInfo:
        """Get user info from auth provider.

        MVP: returns mock data.
        """
        return AuthUserInfo(
            external_id=external_id,
            email=f"{external_id}@mock.local",
            display_name=f"User {external_id[:8]}",
        )
