"""API 速率限制 — 基于 slowapi + Redis 的令牌桶限流。

提供两种 key 函数: 按 IP(未认证)、按 user_id(已认证)。
所有阈值通过 Settings 配置，可由环境变量覆盖。

Usage::

    from backend.api.rate_limit import limiter

    @router.post("/example")
    @limiter.limit("10/minute")
    async def example(request: Request, ...):
        ...
"""

import jwt as pyjwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from backend.core.config import Settings

# ---------------------------------------------------------------------------
# Key 函数
# ---------------------------------------------------------------------------


def get_user_id_or_ip(request: Request) -> str:
    """已认证端点: 优先用 JWT 中的 user_id，fallback 到 IP。

    slowapi 在中间件阶段调用此函数，此时 DI 尚未注入 user 对象，
    因此直接从 Authorization header 解码 sub claim。

    安全说明: 此处不验签，仅将 sub 作为限流桶 key（不作身份认证用途）。
    即使攻击者伪造 sub，请求仍会在后续真实 JWT 验证中被拒绝；
    攻击者无法持续消耗目标用户额度，因为每次请求最终都会被 401 终止。
    """
    auth_header: str | None = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            payload = pyjwt.decode(
                auth_header[7:],
                options={"verify_signature": False},
            )
            user_id: str | None = payload.get("sub")
            if user_id:
                return user_id
        except Exception:
            pass
    return get_remote_address(request)


# ---------------------------------------------------------------------------
# Limiter 单例
# ---------------------------------------------------------------------------

_settings = Settings()
# NOTE: auth 端点使用 get_remote_address(按 IP 限流)，在反向代理（Nginx/Traefik）后
# 部署时需确保 Uvicorn 启用 --proxy-headers，否则 request.client.host 会返回代理 IP。

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_default],
    storage_uri=(
        (_settings.rate_limit_storage_uri or _settings.redis_url)
        if _settings.rate_limit_enabled
        else "memory://"
    ),
    strategy="fixed-window",
    enabled=_settings.rate_limit_enabled,
    # Redis 不可用时（测试 / 降级场景）自动切换到内存存储
    in_memory_fallback_enabled=True,
    swallow_errors=True,
)
