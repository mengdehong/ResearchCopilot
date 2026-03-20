"""Auth API router — user info + settings."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db
from backend.api.schemas.auth import UserInfo
from backend.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SettingsUpdate(BaseModel):
    """Settings update payload."""

    settings: dict


@router.get("/me", response_model=UserInfo)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserInfo:
    """Get current user info from JWT."""
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
    )


@router.put("/settings", response_model=UserInfo)
async def update_settings(
    body: SettingsUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserInfo:
    """Update user settings."""
    current_user.settings = body.settings
    await session.flush()
    await session.commit()
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
    )
