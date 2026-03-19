"""Auth API router — stub."""
from fastapi import APIRouter, Depends

from backend.api.dependencies import get_current_user
from backend.api.schemas.auth import UserInfo
from backend.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=UserInfo)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserInfo:
    """Return current user info from JWT token."""
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
    )
