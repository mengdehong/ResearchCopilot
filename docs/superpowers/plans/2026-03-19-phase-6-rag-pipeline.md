# Phase 6: RAG Pipeline — 细化实施计划

> 离线异步管道：PDF 上传 → MinerU 解析 → 内容分类切块 → LLM 语义增强 → Embedding → 入库。

## 现状盘点

| 已有组件      | 文件                                              | 状态                          |
| ------------- | ------------------------------------------------- | ----------------------------- |
| Parser Engine | `services/parser_engine.py`                       | ✅ MinerU 封装完整             |
| RAG Engine    | `services/rag_engine.py`                          | ✅ 检索 + Embedding + Chunking |
| ORM 内容分表  | `models/paragraph.py`, `table.py`, `figure.py` 等 | ✅ 7 个内容表                  |
| Workers 目录  | `backend/workers/`                                | ⬜ 仅 `__init__.py`            |

> [!NOTE]
> Phase 6 仅依赖 Phase 1（ORM）+ Phase 2（parser_engine, rag_engine），可与 Phase 3/4 并行。

## 设计决策

### 1. Celery Broker
Redis broker + `rpc://` 结果后端。不需持久化结果，状态回写到 documents 表。

### 2. 四阶段管道
单个 Celery 任务 `parse_document` 内串行执行 4 个 Stage。简单可靠，失败回滚方便。

### 3. GPU Worker 隔离
MVP 单 Worker 统一处理。通过 docker-compose profile 区分，有 GPU 用 MinerU，无 GPU 走 PyMuPDF fallback。

---

## Task 1: Celery 配置

### 文件产出

| 文件                            | 说明                   |
| ------------------------------- | ---------------------- |
| `backend/workers/celery_app.py` | Celery 实例 + 基础配置 |
| `backend/workers/__init__.py`   | 导出 celery_app        |

### 关键实现

```python
from celery import Celery
from celery.signals import task_prerun, task_postrun

app = Celery("research_copilot")
app.config_from_object({
    "broker_url": settings.redis_url,
    "result_backend": "rpc://",
    "task_serializer": "json",
    "task_track_started": True,
    "task_acks_late": True,        # 任务失败可重试
    "worker_prefetch_multiplier": 1,  # 长任务不预取
})

@task_prerun.connect
def propagate_trace_id(sender, kwargs, **_):
    """从 kwargs 恢复 trace_id 到 structlog contextvars。"""
    trace_id = kwargs.pop("trace_id", None)
    if trace_id:
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

@task_postrun.connect
def clear_trace_id(sender, **_):
    structlog.contextvars.clear_contextvars()
```

### docker-compose 更新

```yaml
celery-worker:
  build: .
  command: celery -A backend.workers.celery_app worker --loglevel=info --concurrency=2
  depends_on: [redis, postgres]
  environment: *backend-env
```

---

## Task 2: 文档解析任务

### 文件产出

| 文件                                       | 说明           |
| ------------------------------------------ | -------------- |
| `backend/workers/tasks/__init__.py`        | —              |
| `backend/workers/tasks/parse_document.py`  | 文档解析主任务 |
| `tests/integration/test_parse_document.py` | 集成测试       |

### 四阶段管道

```
parse_document(doc_id, trace_id)
│
├─ Stage 1: parser_engine.parse(file_path) → ParsedDocument
│     ├─ 成功：结构化 Markdown + bbox + 图片
│     └─ 失败：PyMuPDF fallback → 纯文本（标记 parse_quality=degraded）
│
├─ Stage 2: 内容分类（规则引擎，不需要 LLM）
│     ├─ abstract/conclusion/discussion/limitations → doc_summaries
│     ├─ 正文段落 → paragraphs（超 1024 tokens 在句子边界分割）
│     ├─ 表格 → tables（raw_data）
│     ├─ 图表 → figures（caption + context）
│     ├─ 公式 → equations（LaTeX + context）
│     ├─ 章节标题 → section_headings（构建层级树）
│     └─ 参考文献 → references
│
├─ Stage 3: LLM 语义增强（可选，失败不阻塞）
│     ├─ 表格 → summary_text + schema_data
│     └─ Contributions → bullet list
│
└─ Stage 4: Embedding + 入库
      ├─ 所有带 text 字段的记录 → rag_engine.embed_batch()
      ├─ 生成 tsvector 全文检索索引
      └─ 批量写入对应分表
```

### 状态回写

```python
async def parse_document(doc_id: str, trace_id: str | None = None) -> None:
    # 更新 parse_status: pending → parsing
    await document_repo.update_status(doc_id, "parsing")
    try:
        # ... 四阶段管道 ...
        await document_repo.update_status(doc_id, "completed")
    except Exception as e:
        await document_repo.update_status(doc_id, "failed")
        logger.error("parse_failed", document_id=doc_id, error=str(e))
        raise
```

### 业务关键日志

按可观测性设计 §2.4：
```python
logger.info("parse_completed",
    document_id=doc_id,
    duration_ms=duration,
    stage_durations={"parse": t1, "classify": t2, "enhance": t3, "embed": t4},
    chunk_counts={"paragraphs": n1, "tables": n2, "figures": n3},
    parse_quality="full" | "degraded",
)
```

### 测试要点

- 集成测试：上传真实 PDF → 验证所有分表有记录
- 验证状态流转 pending → parsing → completed
- 验证失败回写 failed
- 验证 LLM 增强失败时降级（跳过 Stage 3，不阻塞入库）

---

## Task 3: 与 BFF 集成

### 修改文件

| 文件                           | 修改内容                                       |
| ------------------------------ | ---------------------------------------------- |
| `services/document_service.py` | `confirm_upload()` 触发 Celery 任务            |
| `api/routers/document.py`      | `GET /documents/{id}/status` 返回 parse_status |

### 关键改动

```python
# document_service.py
async def confirm_upload(doc_id: UUID, trace_id: str) -> DocumentMeta:
    # ... 校验逻辑 ...
    from backend.workers.tasks.parse_document import parse_document
    parse_document.delay(str(doc_id), trace_id=trace_id)
    return doc
```

---

## 验证清单

| 检查项      | 命令                                                          | 期望         |
| ----------- | ------------------------------------------------------------- | ------------ |
| Celery 启动 | `celery -A backend.workers.celery_app worker --loglevel=info` | Worker ready |
| 解析任务    | 上传 PDF → 查询状态                                           | completed    |
| 内容入库    | 查询 paragraphs 表                                            | 有记录       |
| trace_id    | Worker 日志包含 trace_id                                      | ✅            |
| Lint        | `uv run ruff check backend/workers/`                          | 0 errors     |
