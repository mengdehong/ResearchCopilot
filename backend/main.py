"""Research Copilot — FastAPI entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.middleware import AccessLogMiddleware, RequestIDMiddleware
from backend.api.routers import agent, auth, document, editor, health, workspace
from backend.clients.langgraph_runner import LangGraphRunner
from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.core.exceptions import AppError, app_error_handler
from backend.core.logger import get_logger, setup_logging
from backend.services.llm_gateway import LLMGateway, LLMProvider

logger = get_logger(__name__)


def _build_lg_runner(settings: Settings) -> LangGraphRunner:
    """构建 LangGraph Runner：LLM → 编译图 → Runner。"""
    # 延迟导入避免循环依赖和启动时不需要 agent 包
    from backend.agent.graph import build_supervisor_graph

    gateway = LLMGateway(
        default_provider=LLMProvider(settings.default_llm_provider),
        default_model=settings.default_llm_model,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
    )
    llm = gateway.get_model()
    graph = build_supervisor_graph(llm=llm)
    compiled = graph.compile()
    logger.info("langgraph_compiled", model=settings.default_llm_model)
    return LangGraphRunner(compiled)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: init resources on startup, cleanup on shutdown."""
    settings = Settings()
    setup_logging(debug=settings.debug)

    engine = create_engine(settings.database_url, echo=settings.debug)
    app.state.session_factory = create_session_factory(engine)
    app.state.settings = settings

    # LangGraph Runner（LLM key 缺失时跳过，允许非 Agent 功能正常运行）
    try:
        app.state.lg_runner = _build_lg_runner(settings)
    except (ValueError, ImportError):
        logger.warning(
            "langgraph_runner_init_skipped", reason="LLM key or agent package unavailable"
        )
        app.state.lg_runner = None

    logger.info("application_started", app_name=settings.app_name)
    yield
    if app.state.lg_runner is not None:
        await app.state.lg_runner.shutdown()
    await engine.dispose()
    logger.info("application_stopped")


app = FastAPI(
    title="Research Copilot",
    description="Intent-driven automated desk research workstation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_exception_handler(AppError, app_error_handler)

# Middleware (order matters: outermost first)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

# Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(workspace.router)
app.include_router(document.router)
app.include_router(editor.router)
app.include_router(agent.router)

# Prometheus metrics — auto-collect request latency/QPS/status codes
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except ImportError:
    logger.warning("prometheus_fastapi_instrumentator not installed, skipping metrics")
