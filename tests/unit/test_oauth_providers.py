"""OAuthProvider 抽象 + GitHub/Google 实现单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.clients.oauth.base import OAuthProvider
from backend.clients.oauth.github import GitHubOAuthProvider
from backend.clients.oauth.google import GoogleOAuthProvider


class TestOAuthProviderProtocol:
    """OAuthProvider Protocol 合规性测试。"""

    def test_github_implements_protocol(self) -> None:
        provider = GitHubOAuthProvider(client_id="id", client_secret="secret")
        assert isinstance(provider, OAuthProvider)

    def test_google_implements_protocol(self) -> None:
        provider = GoogleOAuthProvider(client_id="id", client_secret="secret")
        assert isinstance(provider, OAuthProvider)


class TestGitHubOAuthProvider:
    """GitHub OAuth 实现测试。"""

    @pytest.fixture
    def provider(self) -> GitHubOAuthProvider:
        return GitHubOAuthProvider(client_id="gh_id", client_secret="gh_secret")

    def test_get_authorize_url(self, provider: GitHubOAuthProvider) -> None:
        url = provider.get_authorize_url(state="abc123", redirect_uri="http://localhost/callback")
        assert "github.com" in url
        assert "client_id=gh_id" in url
        assert "state=abc123" in url

    @patch("backend.clients.oauth.github.httpx.AsyncClient")
    async def test_exchange_code(
        self, mock_client_cls: MagicMock, provider: GitHubOAuthProvider
    ) -> None:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock token exchange
        token_response = MagicMock()
        token_response.json.return_value = {"access_token": "gho_test123"}
        token_response.raise_for_status = MagicMock()

        # Mock user info
        user_response = MagicMock()
        user_response.json.return_value = {"id": 12345, "login": "testuser", "name": "Test User"}
        user_response.raise_for_status = MagicMock()

        # Mock user emails
        email_response = MagicMock()
        email_response.json.return_value = [
            {"email": "test@github.com", "primary": True, "verified": True},
        ]
        email_response.raise_for_status = MagicMock()

        mock_client.post.return_value = token_response
        mock_client.get.side_effect = [user_response, email_response]

        result = await provider.exchange_code(
            code="code123", redirect_uri="http://localhost/callback"
        )

        assert result["external_id"] == "github:12345"
        assert result["email"] == "test@github.com"
        assert result["display_name"] == "Test User"


class TestGoogleOAuthProvider:
    """Google OAuth 实现测试。"""

    @pytest.fixture
    def provider(self) -> GoogleOAuthProvider:
        return GoogleOAuthProvider(client_id="g_id", client_secret="g_secret")

    def test_get_authorize_url(self, provider: GoogleOAuthProvider) -> None:
        url = provider.get_authorize_url(state="xyz789", redirect_uri="http://localhost/callback")
        assert "accounts.google.com" in url
        assert "client_id=g_id" in url
        assert "state=xyz789" in url

    @patch("backend.clients.oauth.google.httpx.AsyncClient")
    async def test_exchange_code(
        self, mock_client_cls: MagicMock, provider: GoogleOAuthProvider
    ) -> None:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock token exchange
        token_response = MagicMock()
        token_response.json.return_value = {"access_token": "ya29.test123"}
        token_response.raise_for_status = MagicMock()

        # Mock userinfo
        userinfo_response = MagicMock()
        userinfo_response.json.return_value = {
            "sub": "google_abc123",
            "email": "test@gmail.com",
            "name": "Test Google User",
            "email_verified": True,
        }
        userinfo_response.raise_for_status = MagicMock()

        mock_client.post.return_value = token_response
        mock_client.get.return_value = userinfo_response

        result = await provider.exchange_code(
            code="code456", redirect_uri="http://localhost/callback"
        )

        assert result["external_id"] == "google:google_abc123"
        assert result["email"] == "test@gmail.com"
        assert result["display_name"] == "Test Google User"
