"""OAuthProvider 抽象协议 — OAuth 社交登录统一接口。"""

from typing import Protocol, TypedDict, runtime_checkable


class OAuthUserInfo(TypedDict):
    """OAuth 提供商返回的用户信息。"""

    external_id: str
    email: str
    display_name: str


@runtime_checkable
class OAuthProvider(Protocol):
    """OAuth 登录提供商协议。

    实现此协议以支持不同 OAuth 提供商（GitHub、Google 等）。
    """

    provider_name: str

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """生成 OAuth 授权跳转 URL。"""
        ...

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        """用授权码换取用户信息。"""
        ...
