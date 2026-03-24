"""配置加载测试。"""

from backend.core.config import Settings


def test_settings_loads_defaults() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret",
    )
    assert settings.app_name == "Research Copilot"
    assert settings.debug is False
    assert settings.default_llm_provider in {"openai", "anthropic", "google"}
    assert settings.sandbox_timeout_seconds == 120


def test_settings_s3_fields() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret",
        s3_endpoint_url="http://localhost:9000",
    )
    assert settings.s3_endpoint_url == "http://localhost:9000"


def test_celery_timeout_defaults() -> None:
    """Celery 超时和结果过期的默认值应符合生产安全配置。"""
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret",
    )
    assert settings.celery_task_time_limit == 1800
    assert settings.celery_task_soft_time_limit == 1500
    assert settings.celery_result_expires == 86400
