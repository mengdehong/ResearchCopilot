# Phase 8: Integration & Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 端到端集成测试、Docker Compose 全栈编排、CI/CD Pipeline、生产部署配置。

**前置条件：** Phase 0-7 全部完成

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
- [ ] **Step 3: 日志收集** — structlog JSON → stdout → Docker log driver
- [ ] **Step 4: Commit**

---

## 验证清单

| 检查项   | 命令                          | 期望结果         |
| -------- | ----------------------------- | ---------------- |
| 全栈启动 | `docker compose up -d`        | 所有服务 healthy |
| E2E 测试 | `uv run pytest tests/e2e/ -v` | passed           |
| CI 通过  | GitHub Actions                | green            |
| 前端访问 | `curl localhost:80`           | 200 OK           |

---

**Phase 8 完成标志：** 全栈可一键部署 + E2E 测试通过 + CI 绿灯 → **MVP 交付。**
