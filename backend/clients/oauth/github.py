"""GitHub OAuth 提供商实现。"""

from urllib.parse import urlencode

import httpx

from backend.clients.oauth.base import OAuthUserInfo
from backend.core.logger import get_logger

logger = get_logger(__name__)

_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubOAuthProvider:
    """GitHub OAuth 2.0 提供商。"""

    provider_name: str = "github"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """生成 GitHub 授权跳转 URL。"""
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        """用授权码换取 GitHub 用户信息。"""
        async with httpx.AsyncClient() as client:
            # Step 1: code → access_token
            token_resp = await client.post(
                _TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            headers = {"Authorization": f"Bearer {access_token}"}

            # Step 2: 拉取用户基本信息
            user_resp = await client.get(_USER_URL, headers=headers)
            user_resp.raise_for_status()
            user_data = user_resp.json()

            # Step 3: 拉取用户邮箱（可能需要单独 API 调用）
            email_resp = await client.get(_EMAILS_URL, headers=headers)
            email_resp.raise_for_status()
            emails = email_resp.json()
            primary_email = next(
                (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                emails[0]["email"] if emails else f"{user_data['login']}@github.local",
            )

        display_name = user_data.get("name") or user_data.get("login", "GitHub User")
        logger.info("github_oauth_success", github_id=user_data["id"])

        return OAuthUserInfo(
            external_id=f"github:{user_data['id']}",
            email=primary_email,
            display_name=display_name,
        )
