"""Auth schemas — JWT payload and user info DTOs."""
import uuid

from pydantic import BaseModel


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: uuid.UUID
    exp: int


class UserInfo(BaseModel):
    """Public user information response."""

    id: uuid.UUID
    email: str
    display_name: str
