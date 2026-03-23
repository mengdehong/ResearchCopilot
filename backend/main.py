"""Research Copilot — FastAPI entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.middleware import AccessLogMiddleware, RequestIDMiddleware
from backend.api.rate_limit import limiter
from backend.api.routers import agent, auth, document, editor, health, quota, stt, workspace
from backend.clients.langgraph_runner import LangGraphRunner
from backend.core.config import Settings, get_settings
from backend.core.config import settings as _settings
from backend.core.database import create_checkpointer, create_engine, create_session_factory
from backend.core.exceptions import AppError, app_error_handler
from backend.core.logger import get_logger, setup_logging
from backend.services.llm_gateway import LLMGateway, LLMProvider
from backend.services.rag_engine import RAGEngine

logger = get_logger(__name__)


def _build_llm(settings: Settings) -> object:
    """构建 LLM 实例。"""
    gateway = LLMGateway(
        default_provider=LLMProvider(settings.default_llm_provider),
        default_model=settings.default_llm_model,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
    )
    return gateway.get_model()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: init resources on startup, cleanup on shutdown."""
    settings = get_settings()
    setup_logging(debug=settings.debug)

    engine = create_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
    )
    app.state.session_factory = create_session_factory(engine)
    app.state.settings = settings

    # LangGraph Runner（LLM key 缺失时跳过，允许非 Agent 功能正常运行）
    checkpointer_ctx = None
    try:
        from backend.agent.graph import build_supervisor_graph

        llm = _build_llm(settings)
        rag_engine = RAGEngine()
        graph = build_supervisor_graph(
            llm=llm,
            rag_engine=rag_engine,
            session_factory=app.state.session_factory,
        )

        # 创建 checkpointer 并注入图编译（interrupt 需要持久化状态）
        checkpointer_ctx = create_checkpointer(settings.database_url)
        checkpointer = await checkpointer_ctx.__aenter__()
        compiled = graph.compile(checkpointer=checkpointer)
        app.state.lg_runner = LangGraphRunner(compiled)
        logger.info("langgraph_compiled", model=settings.default_llm_model)
    except (ValueError, ImportError) as exc:
        logger.warning(
            "langgraph_runner_init_skipped",
            reason=str(exc),
        )
        app.state.lg_runner = None
        checkpointer_ctx = None
    except Exception as exc:
        logger.error(
            "langgraph_runner_init_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,
        )
        app.state.lg_runner = None
        checkpointer_ctx = None

    logger.info("application_started", app_name=settings.app_name)
    yield
    if app.state.lg_runner is not None:
        await app.state.lg_runner.shutdown()
    if checkpointer_ctx is not None:
        await checkpointer_ctx.__aexit__(None, None, None)
    await engine.dispose()
    logger.info("application_stopped")


app = FastAPI(
    title="Research Copilot",
    description="Intent-driven automated desk research workstation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_exception_handler(AppError, app_error_handler)

# SlowAPI — rate limiting (must be before routers are mounted)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Middleware — registered in innermost-first order (Starlette LIFO: last added = outermost).
# Execution order (outermost → innermost):
#   CORSMiddleware → SlowAPIMiddleware → RequestIDMiddleware → AccessLogMiddleware
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SlowAPIMiddleware)

# CORS must be outermost (registered last) so preflight OPTIONS is handled
# before SlowAPI can return a 429, which would strip CORS headers.
# _settings imported from backend.core.config
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)  # /api/health — 无版本，基础设施探针

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth.router)
v1_router.include_router(workspace.router)
v1_router.include_router(document.router)
v1_router.include_router(editor.router)
v1_router.include_router(agent.router)
v1_router.include_router(stt.router)
v1_router.include_router(quota.router)
app.include_router(v1_router)

# Prometheus metrics — auto-collect request latency/QPS/status codes
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except ImportError:
    logger.warning("prometheus_fastapi_instrumentator not installed, skipping metrics")
