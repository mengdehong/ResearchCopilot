"""LLM 统一封装。多 Provider 适配, 上层只依赖 langchain-core 的 BaseChatModel。"""
import time
from enum import StrEnum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from backend.core.logger import get_logger

logger = get_logger(__name__)


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMGateway:
    """LLM 统一网关。根据 provider 返回对应的 ChatModel 实例。"""

    def __init__(
        self,
        *,
        default_provider: LLMProvider,
        default_model: str,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        google_api_key: str | None = None,
    ) -> None:
        self._default_provider = default_provider
        self._default_model = default_model
        self._keys: dict[LLMProvider, str | None] = {
            LLMProvider.OPENAI: openai_api_key,
            LLMProvider.ANTHROPIC: anthropic_api_key,
            LLMProvider.GOOGLE: google_api_key,
        }

    def get_model(
        self,
        *,
        provider: LLMProvider | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseChatModel:
        """获取 LLM 实例。可覆盖默认 provider 和 model。"""
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

    def invoke(
        self,
        messages: list[BaseMessage],
        *,
        provider: LLMProvider | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseMessage:
        """调用 LLM 并记录结构化日志(model, tokens, latency)。"""
        resolved_provider = provider or self._default_provider
        resolved_model = model or self._default_model
        llm = self.get_model(
            provider=provider, model=model, temperature=temperature,
        )

        start = time.monotonic()
        response = llm.invoke(messages)
        latency_ms = round((time.monotonic() - start) * 1000)

        usage = response.usage_metadata or {}
        logger.info(
            "llm_call_completed",
            provider=resolved_provider,
            model=resolved_model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            latency_ms=latency_ms,
        )
        return response

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
                    model=model, google_api_key=api_key, temperature=temperature,
                )
            case _:
                raise ValueError(f"Unsupported provider: {provider}")
