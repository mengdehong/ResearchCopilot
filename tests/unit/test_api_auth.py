"""Auth API 端点单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_db, get_settings
from backend.main import app


def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.jwt_secret = "test-secret-32-chars-long-enough"
    settings.jwt_algorithm = "HS256"
    settings.access_token_expire_minutes = 30
    settings.refresh_token_expire_days = 14
    settings.resend_api_key = "re_test"
    settings.email_from = "test@test.com"
    settings.frontend_url = "http://localhost:5173"
    settings.oauth_redirect_base_url = "http://localhost:5173"
    settings.github_client_id = "gh_id"
    settings.github_client_secret = "gh_secret"
    settings.google_client_id = "g_id"
    settings.google_client_secret = "g_secret"
    return settings


@pytest.fixture
def test_client() -> TestClient:
    mock_session = AsyncMock()

    async def override_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = _make_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestRegisterEndpoint:
    """POST /api/auth/register"""

    @patch("backend.api.routers.auth.register_user")
    def test_register_success(self, mock_register: AsyncMock, test_client: TestClient) -> None:
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "new@test.com"
        mock_user.display_name = "New User"
        mock_register.return_value = mock_user

        response = test_client.post(
            "/api/auth/register",
            json={
                "email": "new@test.com",
                "password": "Password123",
                "display_name": "New User",
            },
        )
        assert response.status_code == 201
        assert response.json()["message"] == "注册成功，请查收验证邮件"

    @patch("backend.api.routers.auth.register_user")
    def test_register_duplicate_email(
        self, mock_register: AsyncMock, test_client: TestClient
    ) -> None:
        mock_register.side_effect = ValueError("邮箱已注册")

        response = test_client.post(
            "/api/auth/register",
            json={
                "email": "existing@test.com",
                "password": "Password123",
                "display_name": "User",
            },
        )
        assert response.status_code == 409


class TestLoginEndpoint:
    """POST /api/auth/login"""

    @patch("backend.api.routers.auth.login_user")
    def test_login_success(self, mock_login: AsyncMock, test_client: TestClient) -> None:
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@test.com"
        mock_user.display_name = "Test"
        mock_login.return_value = ("access-token", "refresh-token", mock_user)

        response = test_client.post(
            "/api/auth/login",
            json={"email": "test@test.com", "password": "Password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access-token"
        assert data["user"]["email"] == "test@test.com"

    @patch("backend.api.routers.auth.login_user")
    def test_login_wrong_password(self, mock_login: AsyncMock, test_client: TestClient) -> None:
        mock_login.side_effect = ValueError("密码错误")

        response = test_client.post(
            "/api/auth/login",
            json={"email": "test@test.com", "password": "Wrong123"},
        )
        assert response.status_code == 401


class TestVerifyEmailEndpoint:
    """POST /api/auth/verify-email"""

    @patch("backend.api.routers.auth.verify_email_token")
    def test_verify_email_success(self, mock_verify: AsyncMock, test_client: TestClient) -> None:
        mock_verify.return_value = None

        response = test_client.post(
            "/api/auth/verify-email",
            json={"token": "valid-token"},
        )
        assert response.status_code == 200

    @patch("backend.api.routers.auth.verify_email_token")
    def test_verify_email_invalid_token(
        self, mock_verify: AsyncMock, test_client: TestClient
    ) -> None:
        mock_verify.side_effect = ValueError("无效或过期的验证令牌")

        response = test_client.post(
            "/api/auth/verify-email",
            json={"token": "bad-token"},
        )
        assert response.status_code == 400
