# Phase 8: Integration & Deployment — 细化实施计划

> 全栈集成：Docker Compose 编排、E2E 测试、CI/CD、生产部署、监控栈。

## 前置条件

Phase 8 依赖所有前序 Phase 完成。但部分 Task 可提前准备：
- Task 1（Docker Compose）：Phase 0 已有基础编排，可在 Phase 5/6 完成后逐步完善
- Task 3（CI）：lint + unit test 部分可在 Phase 1 完成后就建立

---

## Task 1: Docker Compose 全栈编排

### 服务清单

| 服务               | 镜像/构建                | 端口   | 依赖              |
| ------------------ | ------------------------ | ------ | ----------------- |
| `postgres`         | `pgvector/pgvector:pg16` | 5432   | —                 |
| `redis`            | `redis:7-alpine`         | 6379   | —                 |
| `backend`          | 本地构建（多阶段）       | 8000   | postgres, redis   |
| `langgraph-server` | 本地构建                 | 8123   | postgres          |
| `celery-worker`    | 同 backend 镜像          | —      | postgres, redis   |
| `frontend`         | 本地构建（多阶段）       | 80     | —                 |
| `nginx`            | `nginx:alpine`           | 80/443 | backend, frontend |

### 多阶段 Dockerfile

```dockerfile
# --- Backend ---
FROM python:3.11-slim AS backend-base
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM backend-base AS backend
COPY backend/ backend/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Frontend ---
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm build

FROM nginx:alpine AS frontend
COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY deployment/nginx/frontend.conf /etc/nginx/conf.d/default.conf
```

### 环境变量

```bash
# .env.production 模板
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/research_copilot
REDIS_URL=redis://redis:6379/0
LANGGRAPH_SERVER_URL=http://langgraph-server:8123
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### 健康检查

每个服务配置 `healthcheck`，确保 `docker compose up` 后所有服务 healthy。

---

## Task 2: E2E 集成测试

### 测试场景

| 场景         | 覆盖链路                                      | 验证点                           |
| ------------ | --------------------------------------------- | -------------------------------- |
| 完整研究流程 | 上传 PDF → Discovery → Extraction → Ideation  | artifacts 逐层累积               |
| SSE 事件流   | 发送消息 → 接收 SSE 事件                      | event_type 正确，seq 递增        |
| HITL 交互    | 触发 interrupt → resume → 继续执行            | 状态正确恢复                     |
| Sandbox 执行 | 生成代码 → confirm → 执行 → 结果              | exit_code=0，output_files 有内容 |
| 文档上传     | POST upload-url → PUT S3 → confirm → 解析完成 | parse_status=completed           |
| 认证拦截     | 未认证请求 → 401                              | 所有端点受保护                   |

### 测试框架

```python
# tests/e2e/conftest.py
@pytest.fixture(scope="session")
async def e2e_client():
    """基于 docker compose 环境的 E2E 测试客户端。"""
    async with httpx.AsyncClient(base_url="http://localhost:8000/api") as client:
        yield client

# tests/e2e/test_full_flow.py
async def test_discovery_to_ideation(e2e_client):
    # 1. 创建 workspace
    # 2. 创建 thread
    # 3. 发送 discovery 指令
    # 4. 等待 SSE 的 interrupt 事件
    # 5. Resume with selected papers
    # 6. 验证 artifacts["discovery"] 有内容
```

---

## Task 3: CI Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run ruff check backend/ tests/
      - run: uv run ruff format --check backend/ tests/
      - run: uv run pytest tests/unit/ -v --tb=short

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: cd frontend && pnpm install --frozen-lockfile
      - run: cd frontend && pnpm exec tsc --noEmit
      - run: cd frontend && pnpm exec eslint src/
      - run: cd frontend && pnpm build

  integration:
    runs-on: ubuntu-latest
    needs: [lint-and-test]
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_PASSWORD: test }
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test
```

---

## Task 4: 生产部署配置

### Nginx 反向代理

```nginx
# deployment/nginx/nginx.conf
upstream backend { server backend:8000; }

server {
    listen 80;

    # 前端静态
    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header X-Trace-ID $request_id;
    }

    # SSE (禁用缓冲)
    location ~* /runs/.*/stream$ {
        proxy_pass http://backend;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
```

### 健康检查脚本

```bash
#!/bin/bash
# deployment/healthcheck.sh
curl -sf http://localhost:8000/api/health || exit 1
curl -sf http://localhost:80 || exit 1
```

---

## Task 5: 监控栈部署

### 新增 Docker Compose 服务

| 服务         | 镜像                     | 端口 | 职责             |
| ------------ | ------------------------ | ---- | ---------------- |
| `prometheus` | `prom/prometheus:latest` | 9090 | 抓取 `/metrics`  |
| `loki`       | `grafana/loki:latest`    | 3100 | 接收 Docker 日志 |
| `grafana`    | `grafana/grafana:latest` | 3000 | 统一 Dashboard   |

### Prometheus 配置

```yaml
# deployment/prometheus/prometheus.yml
scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics
    scrape_interval: 15s
```

### 自定义 Metrics 埋点

| 指标名                               | 类型      | 标签              |
| ------------------------------------ | --------- | ----------------- |
| `llm_request_duration_seconds`       | Histogram | model, provider   |
| `sandbox_execution_duration_seconds` | Histogram | exit_code         |
| `agent_workflow_duration_seconds`    | Histogram | workflow_name     |
| `rag_retrieval_duration_seconds`     | Histogram | query_type        |
| `celery_task_duration_seconds`       | Histogram | task_name, status |

### 告警规则（Grafana Alert）

| 告警            | 条件                      | 严重度   |
| --------------- | ------------------------- | -------- |
| 服务不可达      | `/health` 连续 3 次失败   | Critical |
| API 错误率      | 5xx 比率 > 5% 持续 5 分钟 | Warning  |
| LLM 不可用      | LLM 请求失败率 > 50%      | Critical |
| Celery 队列积压 | 待处理任务 > 100          | Warning  |
| DB 连接池耗尽   | 活跃连接 > 80%            | Warning  |
| Sandbox 超时    | 执行超时率 > 20%          | Warning  |

### 预置 Dashboard

1. **系统总览**：QPS、延迟 P50/P95/P99、错误率、服务状态
2. **Agent 运行**：WF 执行时长、HITL 中断次数、重试率
3. **RAG Pipeline**：解析延迟、Embedding 吞吐、检索延迟

---

## 验证清单

| 检查项   | 命令                          | 期望             |
| -------- | ----------------------------- | ---------------- |
| 全栈启动 | `docker compose up -d`        | 所有服务 healthy |
| E2E 测试 | `uv run pytest tests/e2e/ -v` | passed           |
| CI 通过  | GitHub Actions                | green            |
| 前端访问 | `curl localhost:80`           | 200 OK           |
| Metrics  | `curl localhost:8000/metrics` | Prometheus 格式  |
| Grafana  | `curl localhost:3000`         | 200 OK           |
