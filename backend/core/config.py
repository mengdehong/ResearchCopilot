"""全局配置加载。基于 Pydantic BaseSettings, 支持 .env 文件和环境变量。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Research Copilot"
    debug: bool = False
    # --- Database ---
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    # --- Auth ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    # --- OAuth ---
    github_client_id: str | None = None
    github_client_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    oauth_redirect_base_url: str = "http://localhost:5173"
    # --- Email ---
    resend_api_key: str | None = None
    email_from: str = "noreply@researchcopilot.com"
    frontend_url: str = "http://localhost:5173"
    # --- LLM ---
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4o"
    # --- Storage ---
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket_name: str = "research-copilot"
    # --- Sandbox ---
    sandbox_image: str = "research-copilot-sandbox:latest"
    sandbox_timeout_seconds: int = 120
    sandbox_memory_limit: str = "4g"
    sandbox_cpu_count: int = 2
    # --- LangGraph ---
    langgraph_server_url: str = "http://localhost:8123"
    # --- Celery ---
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    # Internal service URL (override in Docker/K8s with container hostname)
    internal_api_url: str = "http://localhost:8000"
    # Secret for signing system-to-system JWT tokens (falls back to jwt_secret)
    internal_token_secret: str | None = None
    # --- LangSmith ---
    langsmith_api_key: str | None = None
    # --- MinerU ---
    mineru_api_url: str = "https://mineru.net/api/v4"
    mineru_api_key: str | None = None
    # --- Groq STT ---
    groq_api_key: str | None = None
    groq_stt_model: str = "whisper-large-v3-turbo"
