# Phase 1: 核心基础设施 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 config、database、logger、异常体系和全部 ORM 模型，建立 Alembic 迁移管线，使后续 Phase 可以直接依赖数据访问层。

**Architecture:** 全局核心组件在 `backend/core/`，ORM 模型在 `backend/models/`，数据库迁移由 Alembic 管理。所有模型统一使用 UUID 主键 + TimestampMixin。

**Tech Stack:** SQLAlchemy 2.0 (async) / asyncpg / Pydantic Settings / structlog / Alembic / pgvector

**对应设计文档：**
- [FastAPI BFF 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-fastapi-bff-design.md) — §三 分层架构, §六 异常处理, §七 数据模型
- [RAG Pipeline 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-rag-pipeline-design.md) — §二 数据模型

---

## 文件结构

```
backend/
├── core/
│   ├── __init__.py
│   ├── config.py              # [NEW] Pydantic BaseSettings 配置加载
│   ├── database.py            # [NEW] SQLAlchemy async engine + session factory
│   ├── logger.py              # [NEW] structlog 结构化日志
│   └── exceptions.py          # [NEW] 自定义异常类型 + 全局异常处理器
│
├── models/
│   ├── __init__.py             # [NEW] 导出所有模型（Alembic 自动发现用）
│   ├── base.py                 # [NEW] 声明基类 + TimestampMixin
│   ├── user.py                 # [NEW] User ORM
│   ├── workspace.py            # [NEW] Workspace ORM
│   ├── thread.py               # [NEW] Thread ORM（本地镜像）
│   ├── document.py             # [NEW] Document 元数据 ORM
│   ├── run_snapshot.py         # [NEW] Run 输入快照 ORM
│   ├── editor_draft.py         # [NEW] 编辑器草稿 ORM
│   ├── quota_record.py         # [NEW] Token 消耗记录 ORM
│   ├── prompt_override.py      # [NEW] Prompt 覆盖层 ORM
│   ├── paragraph.py            # [NEW] RAG 正文段落 ORM
│   ├── doc_summary.py          # [NEW] RAG 文档级索引 ORM
│   ├── table.py                # [NEW] RAG 表格三层 ORM
│   ├── figure.py               # [NEW] RAG 图表 ORM
│   ├── equation.py             # [NEW] RAG 公式 ORM
│   ├── section_heading.py      # [NEW] RAG 章节导航 ORM
│   └── reference.py            # [NEW] RAG 参考文献 ORM
│
├── main.py                     # [MODIFY] 挂载异常处理器、日志初始化
│
alembic/                        # [NEW] 迁移目录
├── alembic.ini
├── env.py
└── versions/

tests/
├── unit/
│   ├── test_config.py          # [NEW]
│   ├── test_exceptions.py      # [NEW]
│   └── test_models.py          # [NEW]
└── integration/
    └── test_database.py        # [NEW] 需要 PostgreSQL
```

---

## Task 1: 配置加载 — config.py

**Files:**
- Create: `backend/core/config.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: 编写失败测试**

`tests/unit/test_config.py`:
```python
"""配置加载测试。"""
from backend.core.config import Settings


def test_settings_loads_defaults() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret",
    )
    assert settings.app_name == "Research Copilot"
    assert settings.debug is False
    assert settings.default_llm_provider == "openai"
    assert settings.sandbox_timeout_seconds == 120


def test_settings_s3_fields() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret",
        s3_endpoint_url="http://localhost:9000",
    )
    assert settings.s3_endpoint_url == "http://localhost:9000"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: FAIL — `ImportError: cannot import name 'Settings'`

- [ ] **Step 3: 实现 config.py**

`backend/core/config.py`:
```python
"""全局配置加载。基于 Pydantic BaseSettings，支持 .env 文件和环境变量。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/core/config.py tests/unit/test_config.py
git commit -m "feat: add Settings config with Pydantic BaseSettings"
```

---

## Task 2: 数据库引擎 — database.py

**Files:**
- Create: `backend/core/database.py`
- Test: `tests/integration/test_database.py`

- [ ] **Step 1: 实现 database.py**

`backend/core/database.py`:
```python
"""PostgreSQL 异步数据库引擎与 Session 工厂。"""
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """创建 SQLAlchemy 异步引擎。"""
    return create_async_engine(
        database_url, echo=echo, pool_size=20, max_overflow=10, pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建 Session 工厂。"""
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """每请求一个 session，请求结束自动关闭。"""
    async with session_factory() as session:
        yield session
```

- [ ] **Step 2: 编写集成测试**

`tests/integration/test_database.py`:
```python
"""数据库连接集成测试（需要运行中的 PostgreSQL）。"""
import pytest
from sqlalchemy import text
from backend.core.database import create_engine, create_session_factory

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/research_copilot"


@pytest.fixture
async def session():
    engine = create_engine(DATABASE_URL)
    factory = create_session_factory(engine)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.integration
async def test_connection(session) -> None:
    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.integration
async def test_pgvector_extension(session) -> None:
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    result = await session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    )
    assert result.scalar() == "vector"
```

- [ ] **Step 3: 运行集成测试（需要 PostgreSQL）**

```bash
docker compose -f deployment/docker-compose.yml up -d postgres
sleep 5
uv run pytest tests/integration/test_database.py -v -m integration
docker compose -f deployment/docker-compose.yml down
```
Expected: `2 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/core/database.py tests/integration/
git commit -m "feat: add async database engine and session factory"
```

---

## Task 3: 结构化日志 — logger.py

**Files:**
- Create: `backend/core/logger.py`

- [ ] **Step 1: 实现 logger.py**

`backend/core/logger.py`:
```python
"""结构化日志配置。基于 structlog，支持 trace_id 串联请求链路。"""
import logging
import sys

import structlog


def setup_logging(*, debug: bool = False) -> None:
    """初始化 structlog 配置。应用启动时调用一次。"""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取结构化 logger 实例。"""
    return structlog.get_logger(name)
```

- [ ] **Step 2: 在 main.py 中调用 setup_logging**

在 `backend/main.py` 的 app 创建前添加：
```python
from backend.core.logger import setup_logging
setup_logging(debug=True)  # 开发模式
```

- [ ] **Step 3: 手动验证日志输出**

```bash
uv run fastapi dev backend/main.py &
sleep 3
curl -s http://localhost:8000/health
# 观察终端日志输出格式为结构化格式
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add backend/core/logger.py backend/main.py
git commit -m "feat: add structlog structured logging with trace_id support"
```

---

## Task 4: 异常体系 — exceptions.py

**Files:**
- Create: `backend/core/exceptions.py`
- Test: `tests/unit/test_exceptions.py`

- [ ] **Step 1: 编写失败测试**

`tests/unit/test_exceptions.py`:
```python
"""异常体系测试。"""
from backend.core.exceptions import (
    AppError, ForbiddenError, NotFoundError, QuotaExceededError,
)


def test_app_error_defaults() -> None:
    err = AppError()
    assert err.status_code == 500
    assert err.error_code == "INTERNAL_ERROR"


def test_not_found_error() -> None:
    err = NotFoundError(message="Document not found")
    assert err.status_code == 404
    assert err.error_code == "NOT_FOUND"
    assert err.message == "Document not found"


def test_forbidden_error() -> None:
    err = ForbiddenError()
    assert err.status_code == 403


def test_quota_exceeded_error() -> None:
    err = QuotaExceededError()
    assert err.status_code == 429
    assert err.error_code == "QUOTA_EXCEEDED"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/unit/test_exceptions.py -v
```
Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 exceptions.py**

`backend/core/exceptions.py`:
```python
"""自定义异常类型与全局异常处理器。"""
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常基类。"""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "Access denied"


class QuotaExceededError(AppError):
    status_code = 429
    error_code = "QUOTA_EXCEEDED"
    message = "Monthly token quota exceeded"


class LangGraphUnavailableError(AppError):
    status_code = 502
    error_code = "AGENT_UNAVAILABLE"
    message = "Agent service is temporarily unavailable"


class InvalidStateTransitionError(AppError):
    status_code = 409
    error_code = "INVALID_STATE"
    message = "Invalid state transition for this resource"


class UploadNotFoundError(AppError):
    status_code = 400
    error_code = "UPLOAD_NOT_FOUND"
    message = "File not found in storage after upload"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """全局异常处理器。挂载到 FastAPI app。"""
    trace_id = getattr(request.state, "trace_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail": exc.message,
            "trace_id": trace_id,
        },
    )
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/unit/test_exceptions.py -v
```
Expected: `4 passed`

- [ ] **Step 5: 在 main.py 中注册全局异常处理器**

在 `backend/main.py` 中追加：
```python
from backend.core.exceptions import AppError, app_error_handler
app.add_exception_handler(AppError, app_error_handler)
```

- [ ] **Step 6: Commit**

```bash
git add backend/core/exceptions.py tests/unit/test_exceptions.py backend/main.py
git commit -m "feat: add exception hierarchy with global error handler"
```

---

## Task 5: ORM 模型 — base.py + BFF 模型 + RAG 模型

**Files:**
- Create: `backend/models/base.py`
- Create: `backend/models/user.py`
- Create: `backend/models/workspace.py`
- Create: `backend/models/thread.py`
- Create: `backend/models/document.py`
- Create: `backend/models/run_snapshot.py`
- Create: `backend/models/editor_draft.py`
- Create: `backend/models/quota_record.py`
- Create: `backend/models/prompt_override.py`
- Create: `backend/models/paragraph.py`
- Create: `backend/models/doc_summary.py`
- Create: `backend/models/table.py`
- Create: `backend/models/figure.py`
- Create: `backend/models/equation.py`
- Create: `backend/models/section_heading.py`
- Create: `backend/models/reference.py`
- Modify: `backend/models/__init__.py`
- Test: `tests/unit/test_models.py`

### Step 5.1: 创建 base.py — 声明基类 + Mixin

`backend/models/base.py`:
```python
"""SQLAlchemy ORM 声明基类与通用 Mixin。"""
import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""
    pass


class TimestampMixin:
    """created_at / updated_at 自动时间戳。"""
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """UUID 主键 Mixin。"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
```

- [ ] **Step 5.1 完成并 commit**

```bash
git add backend/models/base.py
git commit -m "feat: add ORM base class with UUID and Timestamp mixins"
```

### Step 5.2: 创建 BFF 业务模型（6 个文件）

`backend/models/user.py`:
```python
"""用户 ORM（同步自第三方 Auth）。"""
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    external_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
```

`backend/models/workspace.py`:
```python
"""课题空间 ORM。"""
import uuid
from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspaces"

    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    discipline: Mapped[str] = mapped_column(Text, server_default="computer_science", nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
```

`backend/models/thread.py`:
```python
"""对话 Thread ORM（本地镜像）。"""
import uuid
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Thread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "threads"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, server_default="New Thread", nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="creating", nullable=False)
    langgraph_thread_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
```

`backend/models/run_snapshot.py`:
```python
"""Run 输入快照 ORM。"""
import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RunSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "run_snapshots"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False,
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    editor_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default="running", nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

`backend/models/editor_draft.py`:
```python
"""编辑器草稿 ORM。"""
import uuid
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, UUIDPrimaryKeyMixin


class EditorDraft(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "editor_drafts"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), unique=True, nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(server_default="now()", nullable=False)
```

`backend/models/quota_record.py`:
```python
"""Token 消耗记录 ORM。"""
import uuid
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QuotaRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quota_records"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
```

`backend/models/prompt_override.py`:
```python
"""Prompt 覆盖层 ORM。"""
from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PromptOverride(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_overrides"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, server_default="manual", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
```

- [ ] **Step 5.2 完成并 commit**

```bash
git add backend/models/user.py backend/models/workspace.py backend/models/thread.py \
       backend/models/run_snapshot.py backend/models/editor_draft.py \
       backend/models/quota_record.py backend/models/prompt_override.py
git commit -m "feat: add BFF ORM models (user, workspace, thread, run, draft, quota, prompt)"
```

### Step 5.3: 创建 RAG 内容模型（7 个文件）

`backend/models/doc_summary.py`:
```python
"""文档级索引 ORM。"""
import uuid
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.models.base import Base, UUIDPrimaryKeyMixin


class DocSummary(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "doc_summaries"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False,
    )
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
```

`backend/models/paragraph.py`:
```python
"""正文段落 ORM（RAG 证据级检索主力）。"""
import uuid
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.models.base import Base, UUIDPrimaryKeyMixin


class Paragraph(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "paragraphs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False,
    )
    section_path: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_numbers: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
```

`backend/models/table.py`:
```python
"""表格三层 ORM。"""
import uuid
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.models.base import Base, UUIDPrimaryKeyMixin


class Table(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "tables"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False,
    )
    section_path: Mapped[str] = mapped_column(Text, nullable=False)
    table_title: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
```

`backend/models/figure.py`:
```python
"""图表 ORM。"""
import uuid
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.models.base import Base, UUIDPrimaryKeyMixin


class Figure(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "figures"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False,
    )
    section_path: Mapped[str] = mapped_column(Text, nullable=False)
    caption_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
```

`backend/models/equation.py`:
```python
"""数学公式 ORM。"""
import uuid
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.models.base import Base, UUIDPrimaryKeyMixin


class Equation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "equations"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False,
    )
    section_path: Mapped[str] = mapped_column(Text, nullable=False)
    latex_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_text: Mapped[str] = mapped_column(Text, nullable=False)
    equation_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
```

`backend/models/section_heading.py`:
```python
"""章节导航 ORM。"""
import uuid
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.models.base import Base, UUIDPrimaryKeyMixin


class SectionHeading(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "section_headings"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False,
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_text: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("section_headings.id"), nullable=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
```

`backend/models/reference.py`:
```python
"""参考文献 ORM（结构化存储，不做 Embedding）。"""
import uuid
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, UUIDPrimaryKeyMixin


class Reference(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "references"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False,
    )
    ref_index: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_title: Mapped[str] = mapped_column(Text, nullable=False)
    ref_authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref_doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True,
    )
```

`backend/models/document.py`:
```python
"""文档元数据 ORM（BFF + RAG 共用）。"""
import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(Text, server_default="upload", nullable=False)
    doi: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    abstract_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    parse_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    include_appendix: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
```

- [ ] **Step 5.3 完成并 commit**

```bash
git add backend/models/doc_summary.py backend/models/paragraph.py backend/models/table.py \
       backend/models/figure.py backend/models/equation.py backend/models/section_heading.py \
       backend/models/reference.py backend/models/document.py
git commit -m "feat: add RAG content ORM models (doc_summary, paragraph, table, figure, equation, heading, reference, document)"
```

### Step 5.4: 更新 models/__init__.py — 导出所有模型

`backend/models/__init__.py`:
```python
"""导出所有 ORM 模型。Alembic 自动发现 target_metadata 时需要此导入。"""
from backend.models.base import Base
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.models.thread import Thread
from backend.models.document import Document
from backend.models.run_snapshot import RunSnapshot
from backend.models.editor_draft import EditorDraft
from backend.models.quota_record import QuotaRecord
from backend.models.prompt_override import PromptOverride
from backend.models.doc_summary import DocSummary
from backend.models.paragraph import Paragraph
from backend.models.table import Table
from backend.models.figure import Figure
from backend.models.equation import Equation
from backend.models.section_heading import SectionHeading
from backend.models.reference import Reference

__all__ = [
    "Base", "User", "Workspace", "Thread", "Document",
    "RunSnapshot", "EditorDraft", "QuotaRecord", "PromptOverride",
    "DocSummary", "Paragraph", "Table", "Figure", "Equation",
    "SectionHeading", "Reference",
]
```

### Step 5.5: 编写模型导入测试

`tests/unit/test_models.py`:
```python
"""验证所有 ORM 模型可正常导入。"""
from backend.models import (
    Base, User, Workspace, Thread, Document,
    RunSnapshot, EditorDraft, QuotaRecord, PromptOverride,
    DocSummary, Paragraph, Table, Figure, Equation,
    SectionHeading, Reference,
)


def test_all_models_importable() -> None:
    """所有 ORM 模型均可导入。"""
    models = [
        User, Workspace, Thread, Document,
        RunSnapshot, EditorDraft, QuotaRecord, PromptOverride,
        DocSummary, Paragraph, Table, Figure, Equation,
        SectionHeading, Reference,
    ]
    assert len(models) == 15


def test_base_has_metadata() -> None:
    """Base.metadata 应包含所有表名。"""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users", "workspaces", "threads", "documents",
        "run_snapshots", "editor_drafts", "quota_records", "prompt_overrides",
        "doc_summaries", "paragraphs", "tables", "figures",
        "equations", "section_headings", "references",
    }
    assert expected.issubset(table_names)
```

- [ ] **Step 5.5: 运行测试**

```bash
uv run pytest tests/unit/test_models.py -v
```
Expected: `2 passed`

- [ ] **Step 5.6: Commit**

```bash
git add backend/models/ tests/unit/test_models.py
git commit -m "feat: export all ORM models and add import tests"
```

---

## Task 6: Alembic 迁移初始化

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/` (目录)

- [ ] **Step 1: 初始化 Alembic**

```bash
uv run alembic init alembic
```
Expected: 生成 `alembic/` 目录和 `alembic.ini`

- [ ] **Step 2: 修改 alembic.ini 指向 .env**

将 `alembic.ini` 中的 `sqlalchemy.url` 行注释掉（实际 URL 从 env.py 动态加载）：
```ini
# sqlalchemy.url = driver://user:pass@localhost/dbname
```

- [ ] **Step 3: 修改 alembic/env.py 支持异步 + ORM 自动发现**

`alembic/env.py` 关键改动：
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.core.config import Settings
from backend.models import Base  # 导入所有 ORM 模型的 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = Settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 生成初始迁移**

```bash
# 先确保 PostgreSQL 运行
docker compose -f deployment/docker-compose.yml up -d postgres
sleep 5

# 创建 pgvector 扩展（Alembic 不管扩展）
docker exec rc-postgres psql -U postgres -d research_copilot -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 生成迁移
uv run alembic revision --autogenerate -m "initial schema"
```
Expected: 生成 `alembic/versions/xxxx_initial_schema.py`，包含所有 15 张表

- [ ] **Step 5: 执行迁移**

```bash
uv run alembic upgrade head
```
Expected: 无报错，所有表创建成功

- [ ] **Step 6: 验证表已创建**

```bash
docker exec rc-postgres psql -U postgres -d research_copilot -c "\dt"
```
Expected: 列出 users, workspaces, threads, documents, run_snapshots, editor_drafts, quota_records, prompt_overrides, doc_summaries, paragraphs, tables, figures, equations, section_headings, references 等表

- [ ] **Step 7: 清理并 commit**

```bash
docker compose -f deployment/docker-compose.yml down
git add alembic/ alembic.ini
git commit -m "feat: init Alembic with async support and initial schema migration"
```

---

## Task 7: 更新 main.py — 整合所有核心组件

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 更新 main.py**

`backend/main.py`:
```python
"""Research Copilot — FastAPI 启动入口。"""
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.core.exceptions import AppError, app_error_handler
from backend.core.logger import setup_logging, get_logger

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
```

- [ ] **Step 2: 运行全部测试**

```bash
uv run pytest tests/unit/ -v
```
Expected: 所有单元测试通过

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "refactor: integrate core components into FastAPI lifespan"
```

---

## 验证清单

| 检查项       | 命令                                                                 | 期望结果          |
| ------------ | -------------------------------------------------------------------- | ----------------- |
| Config 加载  | `uv run pytest tests/unit/test_config.py -v`                         | 2 passed          |
| 异常体系     | `uv run pytest tests/unit/test_exceptions.py -v`                     | 4 passed          |
| ORM 导入     | `uv run pytest tests/unit/test_models.py -v`                         | 2 passed          |
| DB 连接      | `uv run pytest tests/integration/test_database.py -v -m integration` | 2 passed          |
| Alembic 迁移 | `uv run alembic upgrade head` + `\dt`                                | 15 张表           |
| 全量 lint    | `uv run ruff check backend/ tests/`                                  | 0 errors          |
| FastAPI 启动 | `curl localhost:8000/health`                                         | `{"status":"ok"}` |
| Health 测试  | `uv run pytest tests/unit/test_health.py -v`                         | 1 passed          |

---

**Phase 1 完成标志：** 全部单元测试通过 + Alembic 迁移成功创建 15 张表 + `/health` 返回 200 → 可进入 Phase 2。
