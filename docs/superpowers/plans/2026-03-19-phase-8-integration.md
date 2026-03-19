# Phase 8: Integration & Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 端到端集成测试、Docker Compose 全栈编排、CI/CD Pipeline、生产部署配置、监控栈部署。

**前置条件：** Phase 0-7 全部完成

**对应设计文档：**
- [可观测性设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-observability-design.md) — §四 生产阶段实现

---

## Task 1: Docker Compose 全栈编排

- [ ] **Step 1: 更新 docker-compose.yml** — 添加 backend、celery-worker、frontend 服务
- [ ] **Step 2: 多阶段 Dockerfile** — backend（uv install → uvicorn）、frontend（npm build → nginx）
- [ ] **Step 3: 环境变量注入** — `.env.production` 模板
- [ ] **Step 4: 一键启动验证** — `docker compose up` → 全部服务 healthy
- [ ] **Step 5: Commit**

---

## Task 2: 端到端集成测试

- [ ] **Step 1: 完整研究流程测试** — 上传 PDF → Discovery → Extraction → Ideation
- [ ] **Step 2: SSE 事件流测试** — 发送消息 → 接收流式事件
- [ ] **Step 3: Sandbox 执行测试** — 生成代码 → 确认 → 执行 → 获取结果
- [ ] **Step 4: Commit**

---

## Task 3: CI Pipeline

- [ ] **Step 1: GitHub Actions workflow** — lint + unit tests + build
- [ ] **Step 2: 集成测试 workflow** — docker compose up + pytest（需 PostgreSQL service）
- [ ] **Step 3: Commit**

---

## Task 4: 生产部署配置

- [ ] **Step 1: Nginx 反向代理** — 前端静态 + API 代理 + WebSocket/SSE
- [ ] **Step 2: 健康检查脚本** — 各服务 liveness/readiness
- [ ] **Step 3: 日志收集** — Docker logging driver 配置为 Loki，所有容器日志自动推送
- [ ] **Step 4: Commit**

---

## Task 5: 监控栈部署

> 对应 [可观测性设计 §四](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-observability-design.md)

- [ ] **Step 1: docker-compose 新增 3 个服务** — Prometheus、Loki、Grafana

```yaml
prometheus:    # 抓取 /metrics 端点
loki:          # 接收 Docker 日志
grafana:       # 统一 Dashboard
```

- [ ] **Step 2: Prometheus 配置** — `deployment/prometheus/prometheus.yml`（scrape targets: backend:8000 等）
- [ ] **Step 3: Grafana provisioning** — `deployment/grafana/provisioning/`（自动注册 Prometheus+Loki 数据源 + 预置 Dashboard JSON）
- [ ] **Step 4: 自定义 Metrics 埋点** — 按可观测性设计 §四.3 在 services 层注册 `llm_request_duration_seconds`、`sandbox_execution_duration_seconds`、`agent_workflow_duration_seconds` 等 Prometheus 指标
- [ ] **Step 5: pyproject.toml 追加依赖** — `prometheus-client`
- [ ] **Step 6: 告警规则** — 按可观测性设计 §四.5 在 Grafana 配置 6 条告警（服务不可达、API 错误率、LLM 不可用、队列积压、DB 连接池、Sandbox 超时）
- [ ] **Step 7: 预置 Dashboard** — 系统总览 + Agent 运行 + RAG Pipeline 3 个 Dashboard
- [ ] **Step 8: Commit**

```bash
git commit -m "feat: add Prometheus + Loki + Grafana monitoring stack"
```

---

## 验证清单

| 检查项   | 命令                          | 期望结果         |
| -------- | ----------------------------- | ---------------- |
| 全栈启动 | `docker compose up -d`        | 所有服务 healthy |
| E2E 测试 | `uv run pytest tests/e2e/ -v` | passed           |
| CI 通过  | GitHub Actions                | green            |
| 前端访问 | `curl localhost:80`           | 200 OK           |
| Metrics  | `curl localhost:8000/metrics` | Prometheus 格式  |
| Grafana  | `curl localhost:3000`         | 200 OK           |

---

**Phase 8 完成标志：** 全栈可一键部署 + E2E 测试通过 + CI 绿灯 + 监控 Dashboard 可用 → **MVP 交付。**
