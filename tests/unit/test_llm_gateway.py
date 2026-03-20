"""LLM Gateway 测试 — 覆盖 Tier 路由、Fallback、Structured Output、向后兼容。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.services.llm_gateway import (
    LLMConfig,
    LLMGateway,
    LLMProvider,
    LLMUnavailableError,
    ModelTier,
    ProviderConfig,
    StructuredOutputError,
    TierConfig,
)


# ── Fixtures ──


def _make_config(
    *,
    max_retries: int = 2,
    retry_base_seconds: float = 0.01,
) -> LLMConfig:
    """创建测试用 LLMConfig。"""
    return LLMConfig(
        tiers={
            ModelTier.REASONING: TierConfig(
                providers=[
                    ProviderConfig(provider=LLMProvider.OPENAI, model="gpt-5.4", api_key="sk-r1"),
                    ProviderConfig(
                        provider=LLMProvider.ANTHROPIC,
                        model="claude-sonnet-4.6",
                        api_key="sk-r2",
                    ),
                ]
            ),
            ModelTier.FAST: TierConfig(
                providers=[
                    ProviderConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-5.4-mini",
                        api_key="sk-f1",
                    ),
                ]
            ),
        },
        max_retries=max_retries,
        retry_base_seconds=retry_base_seconds,
    )


# ── 向后兼容 ──


class TestLegacyCompat:
    """旧签名（无 LLMConfig）仍可用。"""

    def test_get_model_openai(self) -> None:
        gateway = LLMGateway(
            openai_api_key="sk-test",
            default_provider=LLMProvider.OPENAI,
            default_model="gpt-4o",
        )
        model = gateway.get_model()
        assert model is not None

    def test_get_model_with_override(self) -> None:
        gateway = LLMGateway(
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
            default_provider=LLMProvider.OPENAI,
            default_model="gpt-4o",
        )
        model = gateway.get_model(
            provider=LLMProvider.ANTHROPIC, model="claude-3-5-sonnet-20241022"
        )
        assert model is not None

    def test_get_model_missing_key_raises(self) -> None:
        gateway = LLMGateway(
            default_provider=LLMProvider.OPENAI,
            default_model="gpt-4o",
        )
        with pytest.raises(ValueError, match="API key not configured"):
            gateway.get_model()


# ── Tier 路由 ──


class TestTierRouting:
    """Tier 参数正确路由到对应 Provider。"""

    def test_get_model_by_tier_reasoning(self) -> None:
        gateway = LLMGateway(config=_make_config())
        model = gateway.get_model(tier=ModelTier.REASONING)
        assert model is not None

    def test_get_model_by_tier_fast(self) -> None:
        gateway = LLMGateway(config=_make_config())
        model = gateway.get_model(tier=ModelTier.FAST)
        assert model is not None


# ── Fallback ──


class TestFallback:
    """同 Tier 横向 Fallback + 指数退避。"""

    async def test_invoke_fallback_on_retryable_error(self) -> None:
        gateway = LLMGateway(config=_make_config(max_retries=1, retry_base_seconds=0.001))

        response = AIMessage(content="ok")
        response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

        call_count = 0

        def side_effect(messages: list) -> AIMessage:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise Exception("Error code: 429")
            return response

        with patch.object(gateway, "_create_model") as mock_create:
            mock_model = MagicMock()
            mock_model.invoke = side_effect
            mock_create.return_value = mock_model

            result = await gateway.invoke(
                [HumanMessage(content="test")],
                tier=ModelTier.REASONING,
            )
            assert result.content == "ok"
            # 第一个 provider 失败 1 次后切到第二个
            assert call_count == 2

    async def test_invoke_all_providers_exhausted(self) -> None:
        gateway = LLMGateway(config=_make_config(max_retries=1, retry_base_seconds=0.001))

        with patch.object(gateway, "_create_model") as mock_create:
            mock_model = MagicMock()
            mock_model.invoke = MagicMock(side_effect=Exception("Error code: 500"))
            mock_create.return_value = mock_model

            with pytest.raises(LLMUnavailableError):
                await gateway.invoke(
                    [HumanMessage(content="test")],
                    tier=ModelTier.REASONING,
                )


# ── Structured Output ──


class TestStructuredOutput:
    """invoke_structured 正确解析结构化输出。"""

    async def test_invoke_structured_success(self) -> None:
        from pydantic import BaseModel as PydanticModel

        class TestSchema(PydanticModel):
            name: str
            value: int

        gateway = LLMGateway(config=_make_config())

        mock_result = TestSchema(name="test", value=42)

        with patch.object(gateway, "_create_model") as mock_create:
            mock_model = MagicMock()
            mock_structured = MagicMock()
            mock_structured.invoke = MagicMock(return_value=mock_result)
            mock_model.with_structured_output = MagicMock(return_value=mock_structured)
            mock_create.return_value = mock_model

            result = await gateway.invoke_structured(
                [HumanMessage(content="test")],
                output_schema=TestSchema,
                tier=ModelTier.FAST,
            )
            assert result.name == "test"
            assert result.value == 42

    async def test_invoke_structured_none_raises(self) -> None:
        from pydantic import BaseModel as PydanticModel

        class TestSchema(PydanticModel):
            name: str

        gateway = LLMGateway(config=_make_config())

        with patch.object(gateway, "_create_model") as mock_create:
            mock_model = MagicMock()
            mock_structured = MagicMock()
            mock_structured.invoke = MagicMock(return_value=None)
            mock_model.with_structured_output = MagicMock(return_value=mock_structured)
            mock_create.return_value = mock_model

            with pytest.raises(StructuredOutputError):
                await gateway.invoke_structured(
                    [HumanMessage(content="test")],
                    output_schema=TestSchema,
                    tier=ModelTier.FAST,
                )

    async def test_invoke_structured_requires_config(self) -> None:
        from pydantic import BaseModel as PydanticModel

        class TestSchema(PydanticModel):
            name: str

        gateway = LLMGateway(
            default_provider=LLMProvider.OPENAI,
            default_model="gpt-4o",
            openai_api_key="sk-test",
        )

        with pytest.raises(ValueError, match="requires LLMConfig"):
            await gateway.invoke_structured(
                [HumanMessage(content="test")],
                output_schema=TestSchema,
            )
