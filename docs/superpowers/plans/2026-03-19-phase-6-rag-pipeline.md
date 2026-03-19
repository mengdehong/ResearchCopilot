# Phase 6: RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 实现完整的 RAG Pipeline：Celery 异步 Worker、PDF 解析 → 内容分类切块 → Embedding → 入库。

**Architecture:** Celery Worker 消费上传事件，调用 Phase 2 的 `parser_engine` 和 `rag_engine`，写入 ORM 模型（Phase 1）。

**前置条件：** Phase 1（ORM models）+ Phase 2（parser_engine, rag_engine）

**对应设计文档：**
- [RAG Pipeline 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-rag-pipeline-design.md) — 全文
- [可观测性设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-observability-design.md) — §三.1 trace_id 传播（Celery Worker 部分）

---

## 文件结构

```
backend/
├── workers/
│   ├── __init__.py
│   ├── celery_app.py          # [NEW] Celery 实例配置
│   └── tasks/
│       ├── __init__.py
│       └── parse_document.py  # [NEW] 文档解析异步任务
```

---

## Task 1: Celery 配置

- [ ] **Step 1: 实现 celery_app.py** — Redis 作为 Broker，PostgreSQL 作为结果后端
- [ ] **Step 2: 配置 trace_id 传播** — `task_prerun` signal 从 kwargs 恢复 trace_id 到 structlog contextvars；`task_postrun` signal 清理 contextvars
- [ ] **Step 3: 更新 docker-compose** — 添加 Celery Worker 服务
- [ ] **Step 4: Commit**

---

## Task 2: 文档解析任务

- [ ] **Step 1: 实现 parse_document.py** — 解析 PDF → 内容分类 → 切块 → Embedding → 写入 ORM
- [ ] **Step 2: 实现状态回写** — 更新 `documents.parse_status`（pending → parsing → completed / failed）
- [ ] **Step 3: 添加业务关键日志** — 按可观测性设计 §2.4，任务完成时输出 `task_name`, `document_id`, `duration_ms`, `status` 结构化日志
- [ ] **Step 4: 编写集成测试** — 上传真实 PDF → 验证所有内容表有记录
- [ ] **Step 5: Commit**

---

## Task 3: 与 BFF 集成

- [ ] **Step 1: 文档上传 API 触发 Celery 任务** — `POST /documents/upload` → `parse_document.delay(doc_id, trace_id=trace_id)`（传播 trace_id）
- [ ] **Step 2: 解析状态查询 API** — `GET /documents/{id}/status` → 返回 parse_status
- [ ] **Step 3: Commit**

---

## 验证清单

| 检查项      | 命令                                                          | 期望结果     |
| ----------- | ------------------------------------------------------------- | ------------ |
| Celery 启动 | `celery -A backend.workers.celery_app worker --loglevel=info` | Worker ready |
| 解析任务    | 上传 PDF → 查询状态                                           | completed    |
| 内容入库    | 查询 paragraphs 表                                            | 有记录       |
| trace_id    | 检查 Worker 日志中是否包含 trace_id 字段                      | 包含         |

---

**Phase 6 完成标志：** PDF 上传后自动解析入库 + 解析状态可查询 + Worker 日志含 trace_id → 可进入 Phase 7。
