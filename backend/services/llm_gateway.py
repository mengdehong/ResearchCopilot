"""LLM 统一封装。多 Provider 适配, 上层只依赖 langchain-core 的 BaseChatModel。"""

from enum import StrEnum

from langchain_core.language_models import BaseChatModel


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

        return self._create_model(provider, model, api_key, temperature)

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
