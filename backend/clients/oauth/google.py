"""Google OAuth 提供商实现。"""

from urllib.parse import urlencode

import httpx

from backend.clients.oauth.base import OAuthUserInfo
from backend.core.logger import get_logger

logger = get_logger(__name__)

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthProvider:
    """Google OAuth 2.0 提供商。"""

    provider_name: str = "google"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """生成 Google 授权跳转 URL。"""
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        """用授权码换取 Google 用户信息。"""
        async with httpx.AsyncClient() as client:
            # Step 1: code → access_token
            token_resp = await client.post(
                _TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            # Step 2: 拉取用户信息
            userinfo_resp = await client.get(
                _USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()

        display_name = userinfo.get("name", "Google User")
        logger.info("google_oauth_success", google_sub=userinfo["sub"])

        return OAuthUserInfo(
            external_id=f"google:{userinfo['sub']}",
            email=userinfo["email"],
            display_name=display_name,
        )
