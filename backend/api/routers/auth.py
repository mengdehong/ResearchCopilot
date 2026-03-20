"""Auth API router — 注册/登录/OAuth/密码重置 + 用户信息。"""

import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db, get_settings
from backend.api.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserInfo,
    VerifyEmailRequest,
)
from backend.clients.email_service.base import EmailService
from backend.clients.email_service.resend_client import ResendEmailService
from backend.clients.oauth.github import GitHubOAuthProvider
from backend.clients.oauth.google import GoogleOAuthProvider
from backend.core.config import Settings
from backend.models.user import User
from backend.services.auth_service import (
    login_user,
    logout_user,
    oauth_login_or_register,
    refresh_access_token,
    register_user,
    request_password_reset,
    reset_password,
    verify_email_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Factory helpers (DI)
# ---------------------------------------------------------------------------


class SettingsUpdate(BaseModel):
    """Settings update payload."""

    settings: dict


def get_email_service(settings: Settings = Depends(get_settings)) -> EmailService:
    """获取邮件服务实例。"""
    return ResendEmailService(
        api_key=settings.resend_api_key or "",
        from_email=settings.email_from,
        frontend_url=settings.frontend_url,
    )


# ---------------------------------------------------------------------------
# 注册 / 登录
# ---------------------------------------------------------------------------


@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    email_service: EmailService = Depends(get_email_service),
) -> MessageResponse:
    """用户邮箱注册。"""
    try:
        await register_user(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            session=session,
            email_service=email_service,
            jwt_secret=settings.jwt_secret,
            jwt_algorithm=settings.jwt_algorithm,
        )
        await session.commit()
        return MessageResponse(message="注册成功，请查收验证邮件")
    except ValueError as e:
        status = 409 if "已注册" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e)) from e


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """邮箱密码登录。"""
    try:
        access_token, refresh_token, user = await login_user(
            email=body.email,
            password=body.password,
            session=session,
            jwt_secret=settings.jwt_secret,
            jwt_algorithm=settings.jwt_algorithm,
            access_expire_minutes=settings.access_token_expire_minutes,
            refresh_expire_days=settings.refresh_token_expire_days,
        )
        await session.commit()

        # refresh token → httpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 86400,
            path="/api/auth",
        )

        return LoginResponse(
            access_token=access_token,
            user=UserInfo(id=user.id, email=user.email, display_name=user.display_name),
        )
    except ValueError as e:
        msg = str(e)
        status = 403 if "未验证" in msg else 401
        raise HTTPException(status_code=status, detail=msg) from e


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """使用 HttpOnly cookie 中的 refresh_token 获取新 access_token。"""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="未提供刷新令牌")
    try:
        new_access = await refresh_access_token(
            refresh_token=refresh_token,
            session=session,
            jwt_secret=settings.jwt_secret,
            jwt_algorithm=settings.jwt_algorithm,
            access_expire_minutes=settings.access_token_expire_minutes,
        )
        await session.commit()
        return TokenResponse(access_token=new_access)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """登出并清理 cookie + 使 refresh token 失效。"""
    if refresh_token:
        await logout_user(refresh_token=refresh_token, session=session)
        await session.commit()

    response.delete_cookie(
        key="refresh_token", path="/api/auth", httponly=True, secure=True, samesite="lax"
    )
    return MessageResponse(message="已登出")


# ---------------------------------------------------------------------------
# 邮箱验证
# ---------------------------------------------------------------------------


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    """验证邮箱。"""
    try:
        await verify_email_token(
            token=body.token,
            jwt_secret=settings.jwt_secret,
            jwt_algorithm=settings.jwt_algorithm,
            session=session,
        )
        await session.commit()
        return MessageResponse(message="邮箱验证成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# 密码重置
# ---------------------------------------------------------------------------


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    email_service: EmailService = Depends(get_email_service),
) -> MessageResponse:
    """请求密码重置。"""
    await request_password_reset(
        email=body.email,
        session=session,
        email_service=email_service,
        jwt_secret=settings.jwt_secret,
        jwt_algorithm=settings.jwt_algorithm,
    )
    await session.commit()
    return MessageResponse(message="如果邮箱已注册，您将收到密码重置邮件")


@router.post("/reset-password", response_model=MessageResponse)
async def do_reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    """重置密码。"""
    try:
        await reset_password(
            token=body.token,
            new_password=body.new_password,
            session=session,
            jwt_secret=settings.jwt_secret,
            jwt_algorithm=settings.jwt_algorithm,
        )
        await session.commit()
        return MessageResponse(message="密码重置成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

_OAUTH_PROVIDERS: dict[str, type] = {
    "github": GitHubOAuthProvider,
    "google": GoogleOAuthProvider,
}


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(
    provider: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """生成 OAuth 授权 URL。"""
    if provider not in _OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 OAuth 提供商: {provider}")

    client_id = getattr(settings, f"{provider}_client_id", None)
    client_secret = getattr(settings, f"{provider}_client_secret", None)
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail=f"{provider} OAuth 未配置")

    oauth = _OAUTH_PROVIDERS[provider](client_id=client_id, client_secret=client_secret)
    state = secrets.token_urlsafe(32)
    redirect_uri = f"{settings.oauth_redirect_base_url}/api/auth/oauth/{provider}/callback"
    url = oauth.get_authorize_url(state=state, redirect_uri=redirect_uri)

    return {"authorize_url": url, "state": state}


@router.post("/oauth/{provider}/callback", response_model=LoginResponse)
async def oauth_callback(
    provider: str,
    code: str,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """OAuth 回调处理。"""
    if provider not in _OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 OAuth 提供商: {provider}")

    client_id = getattr(settings, f"{provider}_client_id", None)
    client_secret = getattr(settings, f"{provider}_client_secret", None)
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail=f"{provider} OAuth 未配置")

    oauth = _OAUTH_PROVIDERS[provider](client_id=client_id, client_secret=client_secret)
    redirect_uri = f"{settings.oauth_redirect_base_url}/api/auth/oauth/{provider}/callback"

    try:
        user_info = await oauth.exchange_code(code=code, redirect_uri=redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth 授权失败: {e}") from e

    try:
        access_token, refresh_token, user = await oauth_login_or_register(
            external_id=user_info["external_id"],
            email=user_info["email"],
            display_name=user_info["display_name"],
            provider=provider,
            session=session,
            jwt_secret=settings.jwt_secret,
            jwt_algorithm=settings.jwt_algorithm,
            access_expire_minutes=settings.access_token_expire_minutes,
            refresh_expire_days=settings.refresh_token_expire_days,
        )
        await session.commit()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )
    return LoginResponse(
        access_token=access_token,
        user=UserInfo(id=user.id, email=user.email, display_name=user.display_name),
    )


# ---------------------------------------------------------------------------
# 用户信息（保留原有端点）
# ---------------------------------------------------------------------------


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
