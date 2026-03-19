"""Research Copilot — FastAPI entry point."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.middleware import AccessLogMiddleware, RequestIDMiddleware
from backend.api.routers import agent, auth, document, editor, health, workspace
from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.core.exceptions import AppError, app_error_handler
from backend.core.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: init resources on startup, cleanup on shutdown."""
    settings = Settings()
    setup_logging(debug=settings.debug)

    engine = create_engine(settings.database_url, echo=settings.debug)
    app.state.session_factory = create_session_factory(engine)
    app.state.settings = settings

    logger.info("application_started", app_name=settings.app_name)
    yield
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
