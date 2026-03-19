# Phase 0: 项目脚手架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建完整的项目目录骨架、依赖管理、开发工具链和基础 Docker 编排，使项目可被 `uv` 管理并通过 CI lint。

**Architecture:** monorepo 结构——`backend/` 为 Python 包，`frontend/` 为独立 Vite 项目，`deployment/` 存放 Docker 相关文件。

**Tech Stack:** Python 3.11+ / uv / ruff / pytest / Docker / docker-compose

**对应设计文档：**
- [ARCHITECT.md](file:///home/wenmou/Projects/ResearchCopilot/ARCHITECT.md) — §一 文件组织

---

## 文件结构

本阶段新建的文件清单：

```
.
├── pyproject.toml                       # [NEW] Python 项目配置 + 依赖声明
├── .python-version                      # [NEW] Python 版本锁定
├── .env.example                         # [NEW] 环境变量模板
├── .gitignore                           # [MODIFY] 追加 Python/Node 忽略规则
├── ruff.toml                            # [NEW] Ruff lint + format 配置
├── pytest.ini                           # [NEW] pytest 配置（或写入 pyproject.toml）
│
├── backend/                             # [NEW] Python 包根目录
│   ├── __init__.py                      # [NEW] 标记为 Python 包
│   ├── main.py                          # [NEW] FastAPI 入口（最小可运行）
│   ├── core/                            # [NEW] 全局核心目录
│   │   └── __init__.py
│   ├── api/                             # [NEW] API 层目录
│   │   ├── __init__.py
│   │   ├── schemas/
│   │   │   └── __init__.py
│   │   └── routers/
│   │       └── __init__.py
│   ├── agent/                           # [NEW] Agent 层目录
│   │   ├── __init__.py
│   │   ├── workflows/
│   │   │   └── __init__.py
│   │   ├── tools/
│   │   │   └── __init__.py
│   │   ├── prompts/                     # [NEW] 目录，无 __init__
│   │   └── skills/
│   │       └── __init__.py
│   ├── services/                        # [NEW] 服务层目录
│   │   └── __init__.py
│   ├── workers/                         # [NEW] 异步任务目录
│   │   ├── __init__.py
│   │   └── tasks/
│   │       └── __init__.py
│   └── repositories/                    # [NEW] Repository 层目录
│       └── __init__.py
│
├── deployment/                          # [NEW] 部署编排目录
│   ├── docker-compose.yml               # [NEW] 基础服务编排（PG + Redis）
│   └── sandbox_image/                   # [NEW] 沙盒 Dockerfile 目录
│       └── .gitkeep
│
├── tests/                               # [NEW] 测试根目录
│   ├── __init__.py
│   ├── conftest.py                      # [NEW] 共享 fixtures
│   └── unit/
│       ├── __init__.py
│       └── test_health.py               # [NEW] 烟雾测试
│
└── frontend/                            # [NEW] 前端项目（Phase 7 填充，此处仅建目录）
    └── .gitkeep
```

---

## Task 1: 初始化 pyproject.toml 与 Python 环境

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`

- [ ] **Step 1: 创建 .python-version**

```
3.11
```

- [ ] **Step 2: 创建 pyproject.toml**

```toml
[project]
name = "research-copilot"
version = "0.1.0"
description = "意图驱动型自动案头研究工作站"
requires-python = ">=3.11"
dependencies = [
    # --- Web Framework ---
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    # --- Database ---
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    # --- Agent ---
    "langgraph>=0.4.0",
    "langchain-core>=0.3.0",
    "langchain-openai>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "langchain-google-genai>=2.1.0",
    # --- RAG ---
    "pgvector>=0.3.6",
    "sentence-transformers>=3.4.0",
    # --- Task Queue ---
    "celery[redis]>=5.4.0",
    # --- Docker ---
    "docker>=7.1.0",
    # --- Config ---
    "pydantic-settings>=2.7.0",
    # --- Logging ---
    "structlog>=24.4.0",
    # --- HTTP ---
    "httpx>=0.28.0",
    # --- Auth ---
    "pyjwt[crypto]>=2.10.0",
    # --- Storage ---
    "boto3>=1.35.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "httpx>=0.28.0",  # TestClient 依赖
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["backend"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests",
    "integration: Integration tests (require external services)",
]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

- [ ] **Step 3: 用 uv 初始化虚拟环境并安装依赖**

```bash
uv sync
```

Expected: 创建 `.venv/` 并安装所有依赖，无报错。

- [ ] **Step 4: 验证 Python 环境**

```bash
uv run python -c "import fastapi; import sqlalchemy; import langgraph; print('OK')"
```

Expected: 输出 `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .python-version uv.lock
git commit -m "chore: init pyproject.toml with uv dependency management"
```

---

## Task 2: 代码质量工具链

**Files:**
- Create: `ruff.toml`

- [ ] **Step 1: 创建 ruff.toml**

```toml
target-version = "py311"
line-length = 100

[lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "A",    # flake8-builtins
    "RUF",  # ruff-specific
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
]
ignore = [
    "E501",   # line too long (format handles it)
    "B008",   # do not perform function calls in argument defaults (FastAPI Depends)
]

[lint.isort]
known-first-party = ["backend"]

[format]
quote-style = "double"
indent-style = "space"
```

- [ ] **Step 2: 验证 ruff 可运行**

```bash
uv run ruff check backend/ --preview
uv run ruff format backend/ --check
```

Expected: 无报错（目录为空时自然通过）

- [ ] **Step 3: Commit**

```bash
git add ruff.toml
git commit -m "chore: add ruff lint and format configuration"
```

---

## Task 3: 创建后端目录骨架

**Files:**
- Create: 所有 `backend/` 下的 `__init__.py` 和子目录

- [ ] **Step 1: 批量创建目录和空 __init__.py**

```bash
# 后端 Python 包目录
mkdir -p backend/{core,api/{schemas,routers},agent/{workflows,tools,prompts,skills},services,workers/tasks,repositories}

# 创建 __init__.py（prompts 目录不需要，它存放 .yaml）
for dir in backend backend/core backend/api backend/api/schemas backend/api/routers \
           backend/agent backend/agent/workflows backend/agent/tools backend/agent/skills \
           backend/services backend/workers backend/workers/tasks backend/repositories; do
    touch "$dir/__init__.py"
done
```

- [ ] **Step 2: 创建 backend/main.py — 最小可运行 FastAPI 入口**

```python
"""Research Copilot — FastAPI 启动入口。"""

from fastapi import FastAPI

app = FastAPI(
    title="Research Copilot",
    description="意图驱动型自动案头研究工作站",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
```

- [ ] **Step 3: 验证 FastAPI 能启动**

```bash
uv run fastapi dev backend/main.py --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add backend/
git commit -m "feat: create backend directory skeleton with minimal FastAPI entry"
```

---

## Task 4: 创建测试骨架

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_health.py`

- [ ] **Step 1: 创建测试目录和 conftest.py**

```bash
mkdir -p tests/unit
touch tests/__init__.py tests/unit/__init__.py
```

`tests/conftest.py`:
```python
"""共享测试 fixtures。"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    """创建 FastAPI 同步测试客户端。"""
    return TestClient(app)
```

- [ ] **Step 2: 编写 health 烟雾测试**

`tests/unit/test_health.py`:
```python
"""Health check 端点烟雾测试。"""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: 运行测试验证**

```bash
uv run pytest tests/unit/test_health.py -v
```

Expected: `1 passed`

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add health endpoint smoke test"
```

---

## Task 5: 环境变量模板与 .gitignore

**Files:**
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: 创建 .env.example**

```bash
# ============= 数据库 =============
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/research_copilot
REDIS_URL=redis://localhost:6379/0

# ============= LLM =============
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_API_KEY=AIza-xxx
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o

# ============= Auth =============
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256

# ============= Storage =============
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=research-copilot

# ============= Sandbox =============
SANDBOX_IMAGE=research-copilot-sandbox:latest
SANDBOX_TIMEOUT_SECONDS=120
SANDBOX_MEMORY_LIMIT=4g
SANDBOX_CPU_COUNT=2
```

- [ ] **Step 2: 更新 .gitignore**

追加以下内容到 `.gitignore`：

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
dist/
*.egg

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/

# Node (frontend)
node_modules/
frontend/dist/

# OS
.DS_Store
Thumbs.db

# uv
uv.lock
```

- [ ] **Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: add env template and update gitignore"
```

---

## Task 6: 基础 Docker Compose（PostgreSQL + Redis）

**Files:**
- Create: `deployment/docker-compose.yml`
- Create: `deployment/sandbox_image/.gitkeep`

- [ ] **Step 1: 创建 deployment 目录**

```bash
mkdir -p deployment/sandbox_image
touch deployment/sandbox_image/.gitkeep
```

- [ ] **Step 2: 创建 docker-compose.yml**

`deployment/docker-compose.yml`:
```yaml
version: "3.9"

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: rc-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: research_copilot
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: rc-redis
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    container_name: rc-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data

volumes:
  pgdata:
  redisdata:
  miniodata:
```

- [ ] **Step 3: 验证 compose 配置合法**

```bash
docker compose -f deployment/docker-compose.yml config
```

Expected: 输出规范化 YAML，无报错。

- [ ] **Step 4: 启动并验证服务（可选 — 需要 Docker）**

```bash
docker compose -f deployment/docker-compose.yml up -d
sleep 5
# 检查 PG
docker exec rc-postgres pg_isready -U postgres
# 检查 pgvector 扩展
docker exec rc-postgres psql -U postgres -d research_copilot -c "CREATE EXTENSION IF NOT EXISTS vector;"
# 检查 Redis
docker exec rc-redis redis-cli ping
# 清理
docker compose -f deployment/docker-compose.yml down
```

Expected: PostgreSQL ready, pgvector 扩展创建成功, Redis PONG

- [ ] **Step 5: Commit**

```bash
git add deployment/
git commit -m "chore: add docker-compose with PostgreSQL(pgvector), Redis, MinIO"
```

---

## Task 7: 创建前端占位目录

**Files:**
- Create: `frontend/.gitkeep`

- [ ] **Step 1: 创建前端占位**

```bash
mkdir -p frontend
touch frontend/.gitkeep
```

> 前端项目初始化将在 Phase 7 使用 `npx create-vite` 完成。此处仅确保目录结构完整。

- [ ] **Step 2: Commit**

```bash
git add frontend/
git commit -m "chore: create frontend placeholder directory"
```

---

## Task 8: 全局验证

- [ ] **Step 1: ruff lint 全项目**

```bash
uv run ruff check backend/ tests/ --preview
```

Expected: 无 lint 错误

- [ ] **Step 2: ruff format 检查**

```bash
uv run ruff format backend/ tests/ --check
```

Expected: 格式符合规范

- [ ] **Step 3: pytest 全量运行**

```bash
uv run pytest tests/ -v
```

Expected: `1 passed`

- [ ] **Step 4: FastAPI 启动验证**

```bash
uv run fastapi dev backend/main.py &
sleep 3
curl -s http://localhost:8000/health | python3 -m json.tool
# Expected: {"status": "ok"}
curl -s http://localhost:8000/docs | head -5
# Expected: HTML 页面（Swagger UI）
kill %1
```

- [ ] **Step 5: 最终 Commit**

```bash
git add -A
git commit -m "chore: Phase 0 scaffolding complete"
```

---

## 验证清单

| 检查项         | 命令                                                     | 期望结果          |
| -------------- | -------------------------------------------------------- | ----------------- |
| Python 环境    | `uv run python --version`                                | `Python 3.11.x`   |
| 依赖安装       | `uv run python -c "import fastapi; import langgraph"`    | 无报错            |
| Lint           | `uv run ruff check backend/ tests/`                      | 0 errors          |
| Format         | `uv run ruff format backend/ tests/ --check`             | 0 reformatted     |
| 测试           | `uv run pytest tests/ -v`                                | 1 passed          |
| FastAPI        | `curl localhost:8000/health`                             | `{"status":"ok"}` |
| Docker Compose | `docker compose -f deployment/docker-compose.yml config` | 合法 YAML         |

---

**Phase 0 完成标志：** `uv run pytest` 通过 + `ruff check` 无报错 + `/health` 返回 200 → 可进入 Phase 1。
