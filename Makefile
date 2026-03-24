.PHONY: help install install-backend install-frontend \
       dev dev-backend dev-celery dev-frontend \
       db-migrate db-upgrade db-downgrade db-reset \
       infra infra-down \
       test test-unit test-integration test-ui-mocked test-browser-smoke smoke-seed \
       lint format typecheck \
       docker-up docker-down docker-logs \
       hooks clean

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
BACKEND_HOST  ?= 0.0.0.0
BACKEND_PORT  ?= 8000
FRONTEND_DIR  := frontend
DEPLOY_DIR    := deployment
COMPOSE       := docker compose -p rc -f $(DEPLOY_DIR)/docker-compose.yml
SMOKE_TEST_EMAIL := e2e-smoke@example.com
SMOKE_TEST_PASSWORD := SmokeTest123!
SMOKE_TEST_DISPLAY_NAME := Smoke Tester

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────
help: ## 显示所有可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ──────────────────────────────────────────────
# Install
# ──────────────────────────────────────────────
install: install-backend install-frontend ## 安装全部依赖

install-backend: ## 安装后端 Python 依赖
	uv sync --dev

install-frontend: ## 安装前端 JS 依赖
	cd $(FRONTEND_DIR) && pnpm install

# ──────────────────────────────────────────────
# Local Development
# ──────────────────────────────────────────────
dev: ## 同时启动后端 + Celery + 前端（需要 tmux 或多终端）
	@echo "━━━ 请在三个终端分别运行 ━━━"
	@echo "  Terminal 1:  make dev-backend"
	@echo "  Terminal 2:  make dev-celery"
	@echo "  Terminal 3:  make dev-frontend"
	@echo ""
	@echo "━━━ 或先启动基础设施 ━━━"
	@echo "  make infra          # Docker 启动 PG + Redis + MinIO"
	@echo "  make db-upgrade     # 运行数据库迁移"

dev-backend: ## 启动后端 API（热重载）
	uv run uvicorn backend.main:app --reload --reload-dir backend --host $(BACKEND_HOST) --port $(BACKEND_PORT)

dev-celery: ## 启动 Celery Worker
	uv run celery -A backend.workers.celery_app worker --loglevel=info --concurrency=2

dev-frontend: ## 启动前端 Vite 开发服务器
	cd $(FRONTEND_DIR) && pnpm run dev

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
db-migrate: ## 生成新的数据库迁移文件 (MSG=xxx)
	uv run alembic revision --autogenerate -m "$(MSG)"

db-upgrade: ## 执行数据库迁移到最新版本
	uv run alembic upgrade head

db-downgrade: ## 回退一个数据库迁移版本
	uv run alembic downgrade -1

db-reset: ## 重置数据库（危险！仅限开发环境）
	uv run alembic downgrade base
	uv run alembic upgrade head

# ──────────────────────────────────────────────
# Infrastructure (Docker)
# ──────────────────────────────────────────────
infra: ## 仅启动基础设施（PostgreSQL + Redis + MinIO）
	$(COMPOSE) up -d --force-recreate --remove-orphans postgres redis minio

infra-down: ## 停止基础设施
	$(COMPOSE) down

# ──────────────────────────────────────────────
# Test & Quality
# ──────────────────────────────────────────────
test: ## 运行全部测试
	uv run pytest

test-unit: ## 仅运行单元测试
	uv run pytest -m unit

test-integration: ## 仅运行集成测试
	uv run pytest -m integration

test-ui-mocked: ## 运行前端 mocked Playwright 测试
	cd $(FRONTEND_DIR) && pnpm run test:e2e

smoke-seed: ## 为本地 browser smoke 测试准备已验证用户
	SMOKE_TEST_EMAIL='$(SMOKE_TEST_EMAIL)' \
	SMOKE_TEST_PASSWORD='$(SMOKE_TEST_PASSWORD)' \
	SMOKE_TEST_DISPLAY_NAME='$(SMOKE_TEST_DISPLAY_NAME)' \
	uv run python tests/scripts/seed_smoke_user.py

test-browser-smoke: infra smoke-seed ## 运行本地真实前后端 browser smoke 测试（要求数据库 schema 已存在）
	cd $(FRONTEND_DIR) && \
	SMOKE_ENABLED=1 \
	SMOKE_TEST_EMAIL='$(SMOKE_TEST_EMAIL)' \
	SMOKE_TEST_PASSWORD='$(SMOKE_TEST_PASSWORD)' \
	pnpm run test:e2e:smoke:local

lint: ## Ruff 检查
	uv run ruff check .

format: ## Ruff 格式化
	uv run ruff format .

typecheck: ## MyPy 类型检查
	uv run mypy backend

# ──────────────────────────────────────────────
# Docker Compose (全栈)
# ──────────────────────────────────────────────
docker-up: ## Docker Compose 全栈启动
	$(COMPOSE) up -d --build

docker-down: ## Docker Compose 全栈停止
	$(COMPOSE) down

docker-logs: ## 查看全栈日志（跟随模式）
	$(COMPOSE) logs -f



# ──────────────────────────────────────────────
# Git Hooks
# ──────────────────────────────────────────────
hooks: ## 安装 pre-commit hooks（commit 时 lint，push 时测试）
	uv run pre-commit install --hook-type pre-commit --hook-type pre-push
	@echo "✅ Git hooks installed successfully"

# ──────────────────────────────────────────────
# Clean
# ──────────────────────────────────────────────
clean: ## 清理缓存和构建产物
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf dist
