"""认证服务 — 注册/登录/Token/密码重置核心逻辑（纯函数为主）。"""

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients.email_service.base import EmailService
from backend.core.logger import get_logger
from backend.models.refresh_token import RefreshToken
from backend.models.user import User

logger = get_logger(__name__)

_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-zA-Z])(?=.*\d).{8,}$")


# ---------------------------------------------------------------------------
# 密码哈希
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """bcrypt 哈希密码。"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码是否匹配。"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _validate_password(password: str) -> None:
    """校验密码强度：≥8位，含字母+数字。"""
    if not _PASSWORD_PATTERN.match(password):
        raise ValueError("密码至少 8 位，需包含字母和数字")


# ---------------------------------------------------------------------------
# Token 生成
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: uuid.UUID,
    secret: str,
    algorithm: str,
    expire_minutes: int,
) -> str:
    """签发 access token (JWT)。"""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": now + timedelta(minutes=expire_minutes),
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_refresh_token(
    user_id: uuid.UUID,
    secret: str,
    algorithm: str,
    expire_days: int,
) -> tuple[str, str]:
    """签发 refresh token，返回 (raw_token, sha256_hash)。"""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": now + timedelta(days=expire_days),
        "iat": now,
    }
    raw_token = jwt.encode(payload, secret, algorithm=algorithm)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------


async def register_user(
    *,
    email: str,
    password: str,
    display_name: str,
    session: AsyncSession,
    email_service: EmailService,
    jwt_secret: str,
    jwt_algorithm: str,
) -> User:
    """注册新用户（邮箱+密码）。"""
    _validate_password(password)

    # 检查邮箱是否已存在
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise ValueError("邮箱已注册")

    user = User(
        external_id=f"local:{uuid.uuid4()}",
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        email_verified=False,
        auth_provider="local",
    )
    session.add(user)
    await session.flush()

    # 签发验证邮件 token
    verify_token = jwt.encode(
        {
            "sub": str(user.id),
            "purpose": "email_verify",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        jwt_secret,
        algorithm=jwt_algorithm,
    )
    await email_service.send_verification_email(to=email, token=verify_token)

    logger.info("user_registered", user_id=str(user.id), email=email)
    return user


# ---------------------------------------------------------------------------
# 邮箱验证
# ---------------------------------------------------------------------------


async def verify_email_token(
    *,
    token: str,
    jwt_secret: str,
    jwt_algorithm: str,
    session: AsyncSession,
) -> None:
    """验证邮箱 token 并标记用户已验证。"""
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])
    except jwt.InvalidTokenError:
        raise ValueError("无效或过期的验证令牌") from None

    if payload.get("purpose") != "email_verify":
        raise ValueError("无效的令牌类型")

    user_id = uuid.UUID(payload["sub"])
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("用户不存在")

    user.email_verified = True
    await session.flush()
    logger.info("email_verified", user_id=str(user_id))


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------


async def login_user(
    *,
    email: str,
    password: str,
    session: AsyncSession,
    jwt_secret: str,
    jwt_algorithm: str,
    access_expire_minutes: int,
    refresh_expire_days: int,
) -> tuple[str, str, User]:
    """邮箱密码登录，返回 (access_token, refresh_token, user)。"""
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or user.password_hash is None:
        raise ValueError("用户不存在或未设置密码")

    if not user.email_verified:
        raise ValueError("邮箱未验证，请先验证邮箱")

    if not verify_password(password, user.password_hash):
        raise ValueError("密码错误")

    access_token = create_access_token(
        user_id=user.id,
        secret=jwt_secret,
        algorithm=jwt_algorithm,
        expire_minutes=access_expire_minutes,
    )
    raw_refresh, token_hash = create_refresh_token(
        user_id=user.id,
        secret=jwt_secret,
        algorithm=jwt_algorithm,
        expire_days=refresh_expire_days,
    )

    # 存 refresh token hash
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=refresh_expire_days),
    )
    session.add(rt)
    await session.flush()

    logger.info("user_login", user_id=str(user.id), email=email)
    return access_token, raw_refresh, user


# ---------------------------------------------------------------------------
# Token Refresh & Logout
# ---------------------------------------------------------------------------


async def refresh_access_token(
    *,
    refresh_token: str,
    session: AsyncSession,
    jwt_secret: str,
    jwt_algorithm: str,
    access_expire_minutes: int,
) -> str:
    """使用 refresh token 换取新的 access token。"""
    try:
        payload = jwt.decode(refresh_token, jwt_secret, algorithms=[jwt_algorithm])
    except jwt.InvalidTokenError:
        raise ValueError("无效或过期的刷新令牌") from None

    if payload.get("type") != "refresh":
        raise ValueError("无效的令牌类型")

    user_id = uuid.UUID(payload["sub"])
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # 查数据库
    rt_stmt = select(RefreshToken).where(
        RefreshToken.token_hash == token_hash,
        RefreshToken.user_id == user_id,
        RefreshToken.revoked.is_(False),
    )
    result = await session.execute(rt_stmt)
    rt = result.scalar_one_or_none()

    if not rt or rt.expires_at < datetime.now(UTC):
        raise ValueError("刷新令牌已失效或过期")

    return create_access_token(
        user_id=user_id,
        secret=jwt_secret,
        algorithm=jwt_algorithm,
        expire_minutes=access_expire_minutes,
    )


async def logout_user(
    *,
    refresh_token: str,
    session: AsyncSession,
) -> None:
    """登出：吊销 refresh token。"""
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    result = await session.execute(stmt)
    rt = result.scalar_one_or_none()
    if rt:
        rt.revoked = True
        await session.flush()
        logger.info("user_logout", user_id=str(rt.user_id))


# ---------------------------------------------------------------------------
# 密码重置
# ---------------------------------------------------------------------------


async def request_password_reset(
    *,
    email: str,
    session: AsyncSession,
    email_service: EmailService,
    jwt_secret: str,
    jwt_algorithm: str,
) -> None:
    """请求密码重置（发邮件）。无论邮箱是否存在都返回成功。"""
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        return  # 防枚举

    reset_token = jwt.encode(
        {
            "sub": str(user.id),
            "purpose": "password_reset",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        jwt_secret,
        algorithm=jwt_algorithm,
    )
    await email_service.send_password_reset_email(to=email, token=reset_token)
    logger.info("password_reset_requested", user_id=str(user.id))


async def reset_password(
    *,
    token: str,
    new_password: str,
    session: AsyncSession,
    jwt_secret: str,
    jwt_algorithm: str,
) -> None:
    """重置密码。"""
    _validate_password(new_password)

    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])
    except jwt.InvalidTokenError:
        raise ValueError("无效或过期的重置令牌") from None

    if payload.get("purpose") != "password_reset":
        raise ValueError("无效的令牌类型")

    user_id = uuid.UUID(payload["sub"])
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("用户不存在")

    user.password_hash = hash_password(new_password)
    await session.flush()

    # 吊销该用户所有 refresh token
    rt_stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked.is_(False),
    )
    rt_result = await session.execute(rt_stmt)
    for rt in rt_result.scalars():
        rt.revoked = True
    await session.flush()

    logger.info("password_reset_completed", user_id=str(user_id))


# ---------------------------------------------------------------------------
# OAuth 登录/注册
# ---------------------------------------------------------------------------


async def oauth_login_or_register(
    *,
    external_id: str,
    email: str,
    display_name: str,
    provider: str,
    session: AsyncSession,
    jwt_secret: str,
    jwt_algorithm: str,
    access_expire_minutes: int,
    refresh_expire_days: int,
) -> tuple[str, str, User]:
    """OAuth 登录或注册，返回 (access_token, refresh_token, user)。"""
    # 先按 external_id 查找
    stmt = select(User).where(User.external_id == external_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # 按 email 查找，尝试自动关联
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            if existing.email_verified:
                # 自动关联
                existing.external_id = external_id
                existing.auth_provider = provider
                await session.flush()
                user = existing
                logger.info("oauth_account_linked", user_id=str(user.id), provider=provider)
            else:
                raise ValueError("此邮箱已注册但未验证，请先验证邮箱")
        else:
            # 新建用户
            user = User(
                external_id=external_id,
                email=email,
                display_name=display_name,
                email_verified=True,
                auth_provider=provider,
            )
            session.add(user)
            await session.flush()
            logger.info("oauth_user_created", user_id=str(user.id), provider=provider)

    access_token = create_access_token(
        user_id=user.id,
        secret=jwt_secret,
        algorithm=jwt_algorithm,
        expire_minutes=access_expire_minutes,
    )
    raw_refresh, token_hash = create_refresh_token(
        user_id=user.id,
        secret=jwt_secret,
        algorithm=jwt_algorithm,
        expire_days=refresh_expire_days,
    )
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=refresh_expire_days),
    )
    session.add(rt)
    await session.flush()

    return access_token, raw_refresh, user
