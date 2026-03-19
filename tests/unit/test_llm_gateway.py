"""LLM Gateway 测试。"""
import pytest

from backend.services.llm_gateway import LLMGateway, LLMProvider


def test_get_model_openai() -> None:
    """验证 OpenAI provider 创建正确的模型实例。"""
    gateway = LLMGateway(
        openai_api_key="sk-test",
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
    )
    model = gateway.get_model()
    assert model is not None


def test_get_model_with_override() -> None:
    """验证可以覆盖 provider 和 model。"""
    gateway = LLMGateway(
        openai_api_key="sk-test",
        anthropic_api_key="sk-ant-test",
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
    )
    model = gateway.get_model(provider=LLMProvider.ANTHROPIC, model="claude-3-5-sonnet-20241022")
    assert model is not None


def test_get_model_missing_key_raises() -> None:
    """未配置 API Key 时应抛错。"""
    gateway = LLMGateway(
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
    )
    with pytest.raises(ValueError, match="API key not configured"):
        gateway.get_model()
