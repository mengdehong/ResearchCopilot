"""Research Copilot — FastAPI 启动入口。"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.core.exceptions import AppError, app_error_handler
from backend.core.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理：启动时初始化资源，关闭时清理。"""
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
    description="意图驱动型自动案头研究工作站",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_exception_handler(AppError, app_error_handler)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
