# 本地开发指南

本文档覆盖从零搭建 Research Copilot 本地开发环境的完整流程。

---

## 前置条件

| 工具 | 最低版本 | 安装方式 |
|------|----------|----------|
| Python | 3.11+ | [python.org](https://www.python.org/) 或系统包管理器 |
| uv | 最新 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 18+ | [nvm](https://github.com/nvm-sh/nvm) 或 [fnm](https://github.com/Schniz/fnm) |
| pnpm | 9+ | `corepack enable && corepack prepare pnpm@latest --activate` |
| Docker | 24+ | [Docker Desktop](https://www.docker.com/products/docker-desktop/) 或 Docker Engine |
| Docker Compose | v2 | 随 Docker Desktop 安装，或 `docker compose` 插件 |

---

## 环境搭建

### 1. 克隆仓库

```bash
git clone https://github.com/mengdehong/ResearchCopilot.git
cd ResearchCopilot
git checkout dev  # 开发分支
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填写以下必需项：

```dotenv
# 数据库（默认值即可用于本地 Docker）
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/research_copilot
REDIS_URL=redis://localhost:6379/0

# LLM — 至少配置一个 Provider
OPENAI_API_KEY=sk-xxx
# ANTHROPIC_API_KEY=sk-ant-xxx
# GOOGLE_API_KEY=AIza-xxx
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o

# Auth
JWT_SECRET=local-dev-secret

# MinerU（RAG Pipeline 需要）
MINERU_API_KEY=your-mineru-api-key
```

完整变量说明参考 [.env.example](../.env.example)。

### 3. 安装依赖

```bash
# 一键安装后端 + 前端
make install

# 或分别安装
make install-backend   # uv sync --dev
make install-frontend  # cd frontend && pnpm install
```

### 4. 启动基础设施

Docker Compose 启动 PostgreSQL (pgvector)、Redis、MinIO：

```bash
make infra
```

> **端口映射**
> | 服务 | 端口 |
> |------|------|
> | PostgreSQL | 5432 |
> | Redis | 6379 |
> | MinIO API | 9000 |
> | MinIO Console | 9001 |

### 5. 数据库迁移

```bash
make db-upgrade
```

---

## 日常开发

### 启动服务

需要在 **三个终端** 分别启动：

```bash
# Terminal 1 — 后端 API (http://localhost:8000)
make dev-backend

# Terminal 2 — Celery Worker (RAG 异步任务)
make dev-celery

# Terminal 3 — 前端 Vite Dev Server (http://localhost:5173)
make dev-frontend
```

后端启用了热重载（`--reload`），修改 `backend/` 下代码后自动重启。
前端 Vite 同样支持 HMR。

### API 文档

后端启动后，访问 Swagger UI：

- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 数据库管理

```bash
# 生成新迁移（需提供 MSG 说明）
make db-migrate MSG="add_user_preferences"

# 执行到最新版本
make db-upgrade

# 回退一个版本
make db-downgrade

# 完全重置（⚠️ 删除所有数据）
make db-reset
```

迁移文件位于 `alembic/versions/`，使用 Alembic autogenerate 基于 `backend/models/` 中 ORM 定义自动生成。

---

## 测试

### 后端测试

```bash
make test              # 运行全部
make test-unit         # 仅单元测试 (pytest -m unit)
make test-integration  # 仅集成测试 (pytest -m integration，需要基础设施)
```

测试使用 `pytest` + `pytest-asyncio`，测试文件位于 `tests/` 目录。

### 前端测试

```bash
cd frontend
pnpm test           # Vitest 单元测试 (watch 模式)
pnpm test:ci        # Vitest 单次运行 (CI 模式)
pnpm run test:e2e   # Playwright E2E 测试
```

### 浏览器 Smoke 测试

完整前后端联调的 Smoke 测试需要启动后端 + 基础设施：

```bash
make test-browser-smoke
```

---

## 代码质量

```bash
make lint       # Ruff 静态检查
make format     # Ruff 自动格式化
make typecheck  # MyPy 严格类型检查
```

### Git Hooks

安装 pre-commit hooks，commit 时自动 lint，push 时运行测试：

```bash
make hooks
```

配置文件：[.pre-commit-config.yaml](../.pre-commit-config.yaml)

---

## Docker 全栈部署 (本地)

如需模拟生产环境完整编排：

```bash
make docker-up    # 构建并启动全部服务
make docker-logs  # 查看实时日志
make docker-down  # 停止并清理
```

全栈通过 Nginx 反向代理暴露在 `localhost:8080`。

编排文件：[deployment/docker-compose.yml](../deployment/docker-compose.yml)

---

## 沙盒镜像

Agent Execution WF 需要 Docker 沙盒镜像：

```bash
docker build -t research-copilot-sandbox:latest -f deployment/sandbox_image/Dockerfile deployment/sandbox_image/
```

镜像预装 NumPy、Pandas、PyTorch、Matplotlib、SciPy 等科学计算库，运行时无网络权限。

---

## 清理

```bash
make clean  # 删除 __pycache__、.pytest_cache、构建产物等
```

---

## 常见问题

### pgvector 扩展未安装

如果使用自建 PostgreSQL 而非 Docker 镜像 `pgvector/pgvector:pg16`，需要手动安装：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 端口冲突

基础设施默认端口 5432 / 6379 / 9000 被占用时，可在 `deployment/docker-compose.yml` 中修改映射，同时更新 `.env` 中对应的连接字符串。

### 前端代理配置

前端 Vite 开发服务器已在 `vite.config.ts` 中配置 API 代理到 `localhost:8000`，无需额外配置跨域。
