"""AuthService 核心逻辑单元测试。"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest

from backend.services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    login_user,
    logout_user,
    refresh_access_token,
    register_user,
    verify_email_token,
    verify_password,
)

# ---- 密码哈希 ----


class TestPasswordHashing:
    def test_hash_password_returns_hash(self) -> None:
        hashed = hash_password("mypassword123")
        assert hashed != "mypassword123"
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self) -> None:
        hashed = hash_password("mypassword123")
        assert verify_password("mypassword123", hashed) is True

    def test_verify_password_incorrect(self) -> None:
        hashed = hash_password("mypassword123")
        assert verify_password("wrongpassword", hashed) is False


# ---- Token 生成 ----


class TestTokenCreation:
    def test_create_access_token(self) -> None:
        user_id = uuid.uuid4()
        token = create_access_token(
            user_id=user_id,
            secret="test-secret",
            algorithm="HS256",
            expire_minutes=30,
        )
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_create_refresh_token_returns_tuple(self) -> None:
        user_id = uuid.uuid4()
        raw_token, token_hash = create_refresh_token(
            user_id=user_id,
            secret="test-secret",
            algorithm="HS256",
            expire_days=14,
        )
        assert isinstance(raw_token, str)
        assert token_hash == hashlib.sha256(raw_token.encode()).hexdigest()

    async def test_refresh_access_token_success(self) -> None:
        user_id = uuid.uuid4()
        raw_token, _ = create_refresh_token(
            user_id=user_id, secret="secret", algorithm="HS256", expire_days=14
        )

        session = AsyncMock()
        mock_rt = MagicMock()
        mock_rt.expires_at = datetime.now(UTC) + timedelta(days=1)
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_rt
        session.execute.return_value = result

        new_access = await refresh_access_token(
            refresh_token=raw_token,
            session=session,
            jwt_secret="secret",
            jwt_algorithm="HS256",
            access_expire_minutes=30,
        )
        assert new_access is not None
        payload = jwt.decode(new_access, "secret", algorithms=["HS256"])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    async def test_logout_user(self) -> None:
        raw_token = "some-refresh-token"
        session = AsyncMock()
        mock_rt = MagicMock()
        mock_rt.revoked = False
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_rt
        session.execute.return_value = result

        await logout_user(refresh_token=raw_token, session=session)
        assert mock_rt.revoked is True
        session.flush.assert_awaited_once()


# ---- 注册 ----


class TestRegisterUser:
    async def test_register_success(self) -> None:
        session = AsyncMock()
        email_service = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        await register_user(
            email="test@example.com",
            password="Password123",
            display_name="Test User",
            session=session,
            email_service=email_service,
            jwt_secret="secret",
            jwt_algorithm="HS256",
        )

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        email_service.send_verification_email.assert_awaited_once()

    async def test_register_duplicate_email_raises(self) -> None:
        session = AsyncMock()
        email_service = AsyncMock()
        existing_user = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing_user
        session.execute.return_value = result

        with pytest.raises(ValueError, match="邮箱已注册"):
            await register_user(
                email="test@example.com",
                password="Password123",
                display_name="Test User",
                session=session,
                email_service=email_service,
                jwt_secret="secret",
                jwt_algorithm="HS256",
            )

    async def test_register_weak_password_raises(self) -> None:
        session = AsyncMock()
        email_service = AsyncMock()

        with pytest.raises(ValueError, match="密码"):
            await register_user(
                email="test@example.com",
                password="short",
                display_name="Test User",
                session=session,
                email_service=email_service,
                jwt_secret="secret",
                jwt_algorithm="HS256",
            )


# ---- 邮箱验证 ----


class TestVerifyEmail:
    async def test_verify_email_success(self) -> None:
        user_id = uuid.uuid4()
        token = jwt.encode(
            {
                "sub": str(user_id),
                "purpose": "email_verify",
                "exp": datetime.now(UTC) + timedelta(hours=1),
            },
            "secret",
            algorithm="HS256",
        )
        session = AsyncMock()
        mock_user = MagicMock()
        mock_user.email_verified = False
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_user
        session.execute.return_value = result

        await verify_email_token(
            token=token, jwt_secret="secret", jwt_algorithm="HS256", session=session
        )
        assert mock_user.email_verified is True

    async def test_verify_email_invalid_token_raises(self) -> None:
        session = AsyncMock()
        with pytest.raises(ValueError, match="无效"):
            await verify_email_token(
                token="invalid-token", jwt_secret="secret", jwt_algorithm="HS256", session=session
            )


# ---- 登录 ----


class TestLoginUser:
    async def test_login_success(self) -> None:
        session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password("Password123")
        mock_user.email_verified = True
        mock_user.auth_provider = "local"
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_user
        session.execute.return_value = result

        access_token, refresh_token, user = await login_user(
            email="test@example.com",
            password="Password123",
            session=session,
            jwt_secret="secret",
            jwt_algorithm="HS256",
            access_expire_minutes=30,
            refresh_expire_days=14,
        )

        assert access_token is not None
        assert refresh_token is not None
        assert user.email == "test@example.com"

    async def test_login_wrong_password_raises(self) -> None:
        session = AsyncMock()
        mock_user = MagicMock()
        mock_user.password_hash = hash_password("Password123")
        mock_user.email_verified = True
        mock_user.auth_provider = "local"
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_user
        session.execute.return_value = result

        with pytest.raises(ValueError, match="密码错误"):
            await login_user(
                email="test@example.com",
                password="WrongPass123",
                session=session,
                jwt_secret="secret",
                jwt_algorithm="HS256",
                access_expire_minutes=30,
                refresh_expire_days=14,
            )

    async def test_login_unverified_email_raises(self) -> None:
        session = AsyncMock()
        mock_user = MagicMock()
        mock_user.password_hash = hash_password("Password123")
        mock_user.email_verified = False
        mock_user.auth_provider = "local"
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_user
        session.execute.return_value = result

        with pytest.raises(ValueError, match="邮箱未验证"):
            await login_user(
                email="test@example.com",
                password="Password123",
                session=session,
                jwt_secret="secret",
                jwt_algorithm="HS256",
                access_expire_minutes=30,
                refresh_expire_days=14,
            )
