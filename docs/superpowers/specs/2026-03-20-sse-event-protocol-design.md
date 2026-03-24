# SSE 事件协议设计

> BFF → Frontend 实时通信的统一事件契约，覆盖 Agent Run 生命周期与文档解析状态推送。

---

## 一、设计决策记录

| 决策项   | 选择                      | 排除方案           | 理由                                                          |
| -------- | ------------------------- | ------------------ | ------------------------------------------------------------- |
| 覆盖范围 | Agent Run + 文档解析状态  | 仅 Agent Run       | 文档解析耗时长，SSE 推送比轮询更及时                          |
| 连接模型 | 双通道分离                | 单通道复用         | Run 有明确生命周期，文档事件是 Workspace 级，解耦更清晰       |
| 断线重连 | 客户端状态水合            | Last-Event-ID 续传 | 避免 BFF 维护事件缓冲区，Frontend 已设计 hydrateFromActiveRun |
| 事件格式 | JSON 信封 + typed payload | 纯文本             | 结构化便于前端类型安全消费                                    |
| 序列号   | 通道内单调递增 seq        | 全局 UUID          | seq 轻量，足够断线检测                                        |

---

## 二、双通道架构

### 2.1 通道定义

| 通道               | 端点                                                  | 生命周期                | 触发方                  |
| ------------------ | ----------------------------------------------------- | ----------------------- | ----------------------- |
| **Run 通道**       | `GET /api/agent/threads/:threadId/runs/:runId/stream` | `run_start` → `run_end` | BFF 订阅 LangGraph 事件 |
| **Workspace 通道** | `GET /api/workspaces/:workspaceId/events`             | 页面进入 → 页面离开     | Celery 任务状态回调     |

### 2.2 数据流

```
Run 通道:
  LangGraph Server ──内部事件──► BFF LangGraphClient ──翻译──► SSE Run 事件 ──► Frontend useAgentStream

Workspace 通道:
  Celery Worker ──任务状态回调──► Redis Pub/Sub ──► BFF EventBroadcaster ──► SSE Doc 事件 ──► Frontend useWorkspaceEvents
```

---

## 三、统一事件信封

### 3.1 Wire Format

每条 SSE 消息的 `data` 字段为 JSON 字符串，结构如下：

```python
class SSEEvent(BaseModel):
    """SSE 事件统一信封。"""

    seq: int                    # 通道内单调递增序列号
    event_type: str             # 事件类型标识
    timestamp: str              # ISO 8601 UTC
    payload: dict[str, Any]     # 按 event_type 变化的负载
```

### 3.2 SSE 原始帧格式

```
event: <event_type>
data: {"seq": 1, "event_type": "node_enter", "timestamp": "2026-03-20T07:00:00Z", "payload": {...}}

```

> `event:` 字段与 `event_type` 保持一致，便于 `EventSource.addEventListener` 精确监听。

---

## 四、Run 通道事件目录

### 4.1 事件类型总览

| event_type          | 触发时机               | 生产者         |
| ------------------- | ---------------------- | -------------- |
| `run_start`         | Run 创建并开始执行     | BFF            |
| `node_enter`        | Workflow 节点开始执行  | LangGraph 翻译 |
| `node_exit`         | Workflow 节点执行完毕  | LangGraph 翻译 |
| `token_delta`       | LLM 流式输出增量 token | LangGraph 翻译 |
| `content_generated` | Agent 产出结构化内容   | LangGraph 翻译 |
| `execution_result`  | 沙盒代码执行结果       | LangGraph 翻译 |
| `pdf_highlight`     | RAG 溯源定位           | LangGraph 翻译 |
| `interrupt`         | HITL 人类在环拦截      | LangGraph 翻译 |
| `run_end`           | Run 正常结束           | BFF            |
| `run_error`         | Run 异常终止           | BFF            |

### 4.2 各事件 Payload 定义

```python
# --- Run 生命周期 ---

class RunStartPayload(BaseModel):
    """Run 开始。"""
    run_id: str
    thread_id: str
    workflow: str | None = None     # 首个被路由到的 workflow

class RunEndPayload(BaseModel):
    """Run 正常结束。"""
    run_id: str
    duration_ms: int

class RunErrorPayload(BaseModel):
    """Run 异常终止。"""
    run_id: str
    error_type: str                 # 错误分类: timeout | llm_error | internal
    message: str
    duration_ms: int

# --- 节点级 ---

class NodeEnterPayload(BaseModel):
    """节点开始执行。"""
    node_id: str                    # 全局唯一，如 UUID
    node_name: str                  # 可读名，如 "discovery.search_apis"
    parent_node_id: str | None = None  # 支持嵌套（subgraph 场景）

class NodeExitPayload(BaseModel):
    """节点执行完毕。"""
    node_id: str
    node_name: str
    status: Literal["completed", "failed", "skipped"]
    duration_ms: int

# --- 流式输出 ---

class TokenDeltaPayload(BaseModel):
    """LLM 流式增量 token。"""
    node_name: str
    delta: str                      # 增量文本片段
    role: Literal["assistant", "tool"]

# --- 结构化产物 ---

class ContentGeneratedPayload(BaseModel):
    """Agent 产出结构化内容（报告、笔记等）。"""
    content_type: Literal["markdown", "reading_note", "comparison_matrix", "glossary"]
    content: str                    # Markdown 文本或 JSON 序列化
    target_tab: Literal["editor"] = "editor"

class ExecutionResultPayload(BaseModel):
    """沙盒代码执行结果。"""
    code: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    artifacts: list[str]            # 产出文件路径列表（图表等）
    target_tab: Literal["sandbox"] = "sandbox"

class PdfHighlightPayload(BaseModel):
    """RAG 溯源高亮定位。"""
    document_id: str
    page: int
    bbox: list[float]               # [x0, y0, x1, y1] 归一化坐标
    text_snippet: str
    target_tab: Literal["pdf"] = "pdf"

# --- HITL ---

class InterruptPayload(BaseModel):
    """HITL 人类在环拦截。"""
    interrupt_type: Literal["confirm_execute", "select_papers", "confirm_outline", "confirm_finalize"]
    title: str
    description: str
    data: dict[str, Any]            # 按 interrupt_type 变化的上下文数据
```

### 4.3 前端消费映射

| event_type          | useAgentStore 字段                 | 消费组件              |
| ------------------- | ---------------------------------- | --------------------- |
| `token_delta`       | `messages[]`                       | ChatPanel             |
| `node_enter/exit`   | `cotTree`                          | CoTTree               |
| `content_generated` | `generatedContent`                 | CanvasPanel (Editor)  |
| `execution_result`  | `executionResult`                  | CanvasPanel (Sandbox) |
| `pdf_highlight`     | `pdfHighlight`                     | CanvasPanel (PDF)     |
| `interrupt`         | `interrupt`                        | HITLCard              |
| `run_start/end`     | `currentRunId`, `connectionStatus` | StatusBar             |

---

## 五、Workspace 通道事件目录

### 5.1 事件类型总览

| event_type            | 触发时机               | 生产者        |
| --------------------- | ---------------------- | ------------- |
| `doc_parse_started`   | Celery 任务开始解析    | Redis Pub/Sub |
| `doc_parse_progress`  | 解析进度更新（阶段性） | Redis Pub/Sub |
| `doc_parse_completed` | 解析全部完成           | Redis Pub/Sub |
| `doc_parse_failed`    | 解析失败               | Redis Pub/Sub |

### 5.2 各事件 Payload 定义

```python
class DocParseStartedPayload(BaseModel):
    """文档开始解析。"""
    document_id: str
    filename: str

class DocParseProgressPayload(BaseModel):
    """解析进度更新。"""
    document_id: str
    stage: Literal["downloading", "parsing", "classifying", "embedding"]
    progress_pct: int               # 0-100

class DocParseCompletedPayload(BaseModel):
    """解析完成。"""
    document_id: str
    paragraph_count: int
    figure_count: int
    table_count: int
    duration_ms: int

class DocParseFailedPayload(BaseModel):
    """解析失败。"""
    document_id: str
    error_message: str
    stage: str                      # 失败发生的阶段
```

### 5.3 前端消费

```typescript
// hooks/useWorkspaceEvents.ts
function useWorkspaceEvents(workspaceId: string): void {
  // 1. 创建 EventSource 连接 /api/workspaces/:id/events
  // 2. doc_parse_* 事件 → invalidateQueries(['documents', workspaceId])
  // 3. 可选：更新 Zustand store 中的文档状态显示
  // 4. 页面离开时关闭连接
}
```

---

## 六、断线恢复策略

### 6.1 Run 通道

```
SSE 断线
  → 检测 connectionStatus = 'disconnected'
  → 延迟 1s 后调用 GET /api/agent/threads/:threadId/runs/active
  → 返回 status = 'running'   → 重新连接 SSE（新 EventSource）
  → 返回 status = 'requires_action' → hydrateFromActiveRun() 渲染 HITL 卡片
  → 返回 null                 → Run 已结束，显示历史消息
```

### 6.2 Workspace 通道

```
SSE 断线
  → 延迟 2s 后重新连接
  → 同时 invalidateQueries(['documents']) 强制刷新文档列表
  → 最大重试 5 次，之后降级为 React Query 轮询模式
```

---

## 七、BFF 翻译层实现要点

### 7.1 LangGraph 事件翻译

```python
# clients/langgraph_client.py — stream_run 方法
async def stream_run(
    self,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[SSEEvent, None]:
    """订阅 LangGraph Server 内部事件流，翻译为标准 SSE 事件。"""
    seq = 0
    async for event in self._langgraph_sdk.stream(thread_id, run_id):
        translated = self._translate_event(event)
        if translated:
            seq += 1
            yield SSEEvent(
                seq=seq,
                event_type=translated.event_type,
                timestamp=datetime.now(UTC).isoformat(),
                payload=translated.payload.model_dump(),
            )
```

### 7.2 文档事件广播

```python
# services/event_broadcaster.py
class EventBroadcaster:
    """基于 Redis Pub/Sub 的 Workspace 级事件广播。"""

    async def subscribe(self, workspace_id: str) -> AsyncGenerator[SSEEvent, None]:
        """订阅指定 Workspace 的文档事件。"""
        channel = f"workspace:{workspace_id}:events"
        async for message in self._redis.subscribe(channel):
            yield SSEEvent.model_validate_json(message)

    async def publish(self, workspace_id: str, event: SSEEvent) -> None:
        """发布事件到 Workspace 通道。"""
        channel = f"workspace:{workspace_id}:events"
        await self._redis.publish(channel, event.model_dump_json())
```

---

## 八、与现有 Spec 的对齐

| Spec                 | 对齐内容                                                               |
| -------------------- | ---------------------------------------------------------------------- |
| FastAPI BFF 设计     | §4 Run 通道端点对齐 BFF API 路由，翻译层补充 `langgraph_client.py`     |
| 前端架构设计         | §4.3 消费映射对齐 `useAgentStore` 字段，§6 对齐 `hydrateFromActiveRun` |
| 可观测性设计         | 每条 SSE 事件的 `seq` + `timestamp` 可用于追踪延迟                     |
| LangGraph Agent 设计 | `node_enter/exit` 的 `node_name` 对齐 Workflow 节点命名（`wf.node`）   |
