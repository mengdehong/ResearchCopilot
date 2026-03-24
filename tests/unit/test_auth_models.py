"""User 认证字段扩展 + RefreshToken 模型测试。"""

from sqlalchemy import inspect

from backend.models.base import Base
from backend.models.refresh_token import RefreshToken
from backend.models.user import User


class TestUserAuthFields:
    """User 模型认证字段测试。"""

    def test_user_has_password_hash_column(self) -> None:
        """User 应有 password_hash 可空字段。"""
        mapper = inspect(User)
        col = mapper.columns["password_hash"]
        assert col.nullable is True

    def test_user_has_email_verified_column(self) -> None:
        """User 应有 email_verified 布尔字段。"""
        mapper = inspect(User)
        col = mapper.columns["email_verified"]
        assert col.nullable is False

    def test_user_has_auth_provider_column(self) -> None:
        """User 应有 auth_provider 字段。"""
        mapper = inspect(User)
        col = mapper.columns["auth_provider"]
        assert col.nullable is False


class TestRefreshTokenModel:
    """RefreshToken 模型测试。"""

    def test_refresh_token_importable(self) -> None:
        """RefreshToken 模型可导入。"""
        assert RefreshToken.__tablename__ == "refresh_tokens"

    def test_refresh_token_table_in_metadata(self) -> None:
        """refresh_tokens 表存在于 Base.metadata。"""
        assert "refresh_tokens" in Base.metadata.tables

    def test_refresh_token_has_required_columns(self) -> None:
        """RefreshToken 应有所有必需字段。"""
        mapper = inspect(RefreshToken)
        column_names = set(mapper.columns.keys())
        required = {"id", "user_id", "token_hash", "expires_at", "revoked"}
        assert required.issubset(column_names)

    def test_refresh_token_revoked_defaults_to_false(self) -> None:
        """revoked 字段默认值应为 False。"""
        mapper = inspect(RefreshToken)
        col = mapper.columns["revoked"]
        assert col.default is not None
