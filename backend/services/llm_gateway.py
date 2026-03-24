from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from backend.core.exceptions import LLMServiceError
from backend.core.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage

logger = get_logger(__name__)

_T = TypeVar("_T")

# ── 可重试 HTTP 状态码 ──
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class LLMProvider(StrEnum):
    """LLM Provider 标识。"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelTier(StrEnum):
    """模型能力分级。"""

    REASONING = "reasoning"
    FAST = "fast"


class ProviderConfig(BaseModel):
    """单个 Provider 配置。"""

    provider: LLMProvider
    model: str
    api_key: str
    timeout_seconds: int = 60


class TierConfig(BaseModel):
    """单个 Tier 的 Provider 优先级链。"""

    providers: list[ProviderConfig]


class LLMConfig(BaseModel):
    """LLM Gateway 完整配置。"""

    tiers: dict[ModelTier, TierConfig]
    max_retries: int = 3
    retry_base_seconds: float = 1.0
    retry_multiplier: float = 2.0


class LLMUnavailableError(LLMServiceError):
    """保持向后兼容：下游代码 catch LLMUnavailableError 继续有效。"""


class StructuredOutputError(Exception):
    """LLM 返回的 JSON 无法解析为目标 schema。"""

    def __init__(self, message: str, raw_response: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response


def _is_retryable(error: Exception) -> bool:
    """判断异常是否可重试。"""
    error_str = str(error).lower()
    # 检查超时
    if "timeout" in error_str or isinstance(error, TimeoutError | asyncio.TimeoutError):
        return True
    # 检查 HTTP 状态码
    return any(str(code) in error_str for code in _RETRYABLE_STATUS_CODES)


class LLMGateway:
    """LLM 统一网关。双 Tier 模型池 + 同 Tier 横向 Fallback。"""

    def __init__(
        self,
        *,
        config: LLMConfig | None = None,
        # 向后兼容旧签名
        default_provider: LLMProvider | None = None,
        default_model: str | None = None,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        google_api_key: str | None = None,
    ) -> None:
        if config is not None:
            self._config = config
            # 从 config 提取默认值
            first_tier = next(iter(config.tiers.values()))
            first_provider = first_tier.providers[0]
            self._default_provider = first_provider.provider
            self._default_model = first_provider.model
            self._keys: dict[LLMProvider, str | None] = {}
            for tier_config in config.tiers.values():
                for pc in tier_config.providers:
                    self._keys[pc.provider] = pc.api_key
        else:
            # 旧签名兼容
            assert default_provider is not None, "default_provider required without config"
            assert default_model is not None, "default_model required without config"
            self._default_provider = default_provider
            self._default_model = default_model
            self._keys = {
                LLMProvider.OPENAI: openai_api_key,
                LLMProvider.ANTHROPIC: anthropic_api_key,
                LLMProvider.GOOGLE: google_api_key,
            }
            self._config = None

    def get_model(
        self,
        *,
        tier: ModelTier | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseChatModel:
        """获取 LLM 实例。新用法推荐 tier 参数，旧用法 provider+model 仍有效。"""
        if tier is not None and self._config is not None:
            tier_config = self._config.tiers.get(tier)
            if tier_config is None or not tier_config.providers:
                raise ValueError(f"No providers configured for tier: {tier}")
            pc = tier_config.providers[0]
            return self._create_model(pc.provider, pc.model, pc.api_key, temperature)

        provider = provider or self._default_provider
        model = model or self._default_model
        api_key = self._keys.get(provider)

        if not api_key:
            raise ValueError(f"API key not configured for provider: {provider}")

        logger.info(
            "llm_model_created",
            provider=provider,
            model=model,
            temperature=temperature,
        )
        return self._create_model(provider, model, api_key, temperature)

    async def invoke(
        self,
        messages: list[BaseMessage],
        *,
        tier: ModelTier | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseMessage:
        """调用 LLM，带 Fallback + 重试 + 结构化日志。"""
        # Tier 路由 + Fallback
        if tier is not None and self._config is not None:
            return await self._invoke_with_fallback(messages, tier=tier, temperature=temperature)

        # 旧路径：无 Fallback 单次调用
        resolved_provider = provider or self._default_provider
        resolved_model = model or self._default_model
        llm = self.get_model(
            provider=provider,
            model=model,
            temperature=temperature,
        )

        start = time.monotonic()
        response = await asyncio.to_thread(llm.invoke, messages)
        latency_ms = round((time.monotonic() - start) * 1000)

        usage = response.usage_metadata or {}
        logger.info(
            "llm_call_completed",
            provider=resolved_provider,
            model=resolved_model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            latency_ms=latency_ms,
            is_fallback=False,
        )
        return response

    async def _run_with_provider_fallback(
        self,
        tier: ModelTier,
        *,
        invoke_fn: Callable[[ProviderConfig], Awaitable[_T]],
    ) -> _T:
        """Execute invoke_fn for each provider in tier with retry + exponential backoff.

        Falls back to the next provider in the tier on non-retryable errors or
        when all retries are exhausted. Raises LLMUnavailableError if all providers fail.
        """
        assert self._config is not None
        tier_config = self._config.tiers.get(tier)
        if tier_config is None or not tier_config.providers:
            raise ValueError(f"No providers configured for tier: {tier}")

        last_error: Exception | None = None

        for pc in tier_config.providers:
            for retry in range(self._config.max_retries):
                try:
                    return await invoke_fn(pc)
                except StructuredOutputError:
                    raise
                except Exception as e:
                    last_error = e
                    if not _is_retryable(e):
                        logger.warning(
                            "llm_non_retryable_error",
                            provider=pc.provider,
                            model=pc.model,
                            error_type=type(e).__name__,
                        )
                        break  # 跳到下一个 Provider

                    delay = self._config.retry_base_seconds * (self._config.retry_multiplier**retry)
                    logger.warning(
                        "llm_retry",
                        provider=pc.provider,
                        model=pc.model,
                        retry=retry + 1,
                        delay_seconds=delay,
                        error_type=type(e).__name__,
                    )
                    await asyncio.sleep(delay)

            if last_error is not None:
                logger.warning(
                    "llm_provider_fallback",
                    original_provider=pc.provider,
                    tier=tier,
                    error_type=type(last_error).__name__,
                )

        raise LLMUnavailableError(f"All providers exhausted for tier={tier}: {last_error}")

    async def _invoke_with_fallback(
        self,
        messages: list[BaseMessage],
        *,
        tier: ModelTier,
        temperature: float,
    ) -> BaseMessage:
        """带 Fallback + 指数退避的调用。委托给 _run_with_provider_fallback。"""

        async def _invoke(pc: ProviderConfig) -> BaseMessage:
            llm = self._create_model(pc.provider, pc.model, pc.api_key, temperature)
            start = time.monotonic()
            response = await asyncio.to_thread(llm.invoke, messages)
            latency_ms = round((time.monotonic() - start) * 1000)
            usage = response.usage_metadata or {}
            logger.info(
                "llm_call_completed",
                provider=pc.provider,
                model=pc.model,
                tier=tier,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                latency_ms=latency_ms,
            )
            return response

        return await self._run_with_provider_fallback(tier, invoke_fn=_invoke)

    async def invoke_structured(
        self,
        messages: list[BaseMessage],
        output_schema: type[BaseModel],
        *,
        tier: ModelTier = ModelTier.FAST,
        temperature: float = 0.0,
        max_parse_retries: int = 2,
    ) -> BaseModel:
        """调用 LLM 并解析为结构化输出。

        内部使用 with_structured_output()，统一处理解析失败重试。
        """
        if self._config is None:
            raise ValueError("invoke_structured requires LLMConfig with tier configuration")

        tier_config = self._config.tiers.get(tier)
        if tier_config is None or not tier_config.providers:
            raise ValueError(f"No providers configured for tier: {tier}")

        async def _invoke(pc: ProviderConfig) -> BaseModel:
            llm = self._create_model(pc.provider, pc.model, pc.api_key, temperature)
            structured_llm = llm.with_structured_output(output_schema)

            start = time.monotonic()
            result = await asyncio.to_thread(structured_llm.invoke, messages)
            latency_ms = round((time.monotonic() - start) * 1000)

            if result is None:
                raise StructuredOutputError(
                    "LLM returned None for structured output",
                    raw_response="None",
                )

            usage: dict = getattr(result, "usage_metadata", None) or {}
            logger.info(
                "llm_call_completed",
                provider=pc.provider,
                model=pc.model,
                latency_ms=latency_ms,
                is_structured=True,
                is_fallback=pc != tier_config.providers[0],
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )
            return result

        return await self._run_with_provider_fallback(tier, invoke_fn=_invoke)

    def _create_model(
        self,
        provider: LLMProvider,
        model: str,
        api_key: str,
        temperature: float,
    ) -> BaseChatModel:
        """工厂方法: 根据 provider 创建对应的 ChatModel。"""
        match provider:
            case LLMProvider.OPENAI:
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(model=model, api_key=api_key, temperature=temperature)
            case LLMProvider.ANTHROPIC:
                from langchain_anthropic import ChatAnthropic

                return ChatAnthropic(model=model, api_key=api_key, temperature=temperature)
            case LLMProvider.GOOGLE:
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=api_key,
                    temperature=temperature,
                )
            case _:
                raise ValueError(f"Unsupported provider: {provider}")
