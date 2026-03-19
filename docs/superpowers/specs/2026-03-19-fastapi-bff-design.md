# FastAPI BFF 架构设计

> Research Copilot 的业务控制面，负责鉴权、租户隔离、文件代理、Agent 状态桥接与 SSE 事件翻译。

## 一、设计目标

- **纯 BFF 定位**：只做业务控制面，不运行 Agent 逻辑。Agent 运行时由独立的 LangGraph Server 承载
- **事件翻译层**：将 LangGraph 内部事件协议翻译为前端友好的统一格式，前端不耦合 Agent 框架
- **RESTful 契约**：HTTP 状态码驱动错误语义，无包装体
- **可测试性**：三层分离（Service / Repository / Client），每层可独立 mock 测试

---

## 二、技术决策记录

| 决策项         | 选择                                             | 排除方案                             | 理由                                                     |
| -------------- | ------------------------------------------------ | ------------------------------------ | -------------------------------------------------------- |
| 架构模式       | FastAPI BFF + LangGraph Server 分离部署          | 嵌入模式（LangGraph 编译进 FastAPI） | 职责分离，独立扩缩容，Agent 框架可替换                   |
| LangGraph 通信 | `langgraph-sdk` 底层 HTTP Client                 | `RemoteGraph` 高层抽象               | 对 Thread/Run/Interrupt 生命周期控制更精确，debug 更容易 |
| 认证           | 第三方 Auth 服务（Clerk/Auth0/Supabase Auth）    | 自建用户系统                         | MVP 阶段聚焦 AI 核心能力，认证外包                       |
| 文件上传       | S3/MinIO 预签名 URL 前端直传                     | FastAPI 代理上传                     | 大文件不经过 BFF，减轻带宽压力。云端 S3 / 私有化 MinIO   |
| SSE 流式       | FastAPI 做事件翻译层                             | 纯透传 LangGraph 原始事件            | 前端不耦合 LangGraph 协议，未来可换 Agent 框架           |
| 错误处理       | HTTP 状态码驱动                                  | 统一包装体 `{ code, data, message }` | 前端 React SPA，RESTful 风格更自然                       |
| 编辑器同步     | 用户触发提交（Agent 输入）+ 防抖自动保存（草稿） | 纯被动/纯自动                        | 两条通道互不干扰，语义清晰                               |
| 数据访问       | Repository 模式                                  | Service 直接操作 SQLAlchemy          | 数据访问隔离，方便测试替换为内存实现                     |

---

## 三、分层架构

### 3.1 总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Middleware Pipeline                         │
│  CORSMiddleware → RequestID → AccessLog → RateLimit(粗粒度)    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                     Router Layer (api/routers/)                  │
│  auth.py | agent.py | document.py | workspace.py | editor.py   │
│  职责：HTTP 关注点 — 请求解析、响应序列化、依赖注入调度         │
│  原则：不含业务逻辑，只做"接线员"                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ 调用
┌────────────────────────────▼────────────────────────────────────┐
│                     Service Layer (services/)                    │
│  agent_service.py | document_service.py | workspace_service.py  │
│  editor_service.py | quota_service.py                           │
│  职责：业务编排 — 流程协调、事件翻译、状态管理                   │
│  原则：纯逻辑函数，不感知 HTTP，依赖通过参数注入                │
└────────────┬───────────────────────────────────┬────────────────┘
             │ 数据访问                          │ 外部系统
┌────────────▼────────────────┐    ┌─────────────▼────────────────┐
│ Repository Layer (repos/)    │    │ Client Layer (clients/)       │
│ base.py (泛型 CRUD 基类)     │    │ langgraph_client.py           │
│ user_repo.py                 │    │ storage_client.py             │
│ workspace_repo.py            │    │ auth_client.py                │
│ document_repo.py             │    │                               │
│ editor_repo.py               │    │ 职责：封装第三方 SDK 和协议   │
│ run_snapshot_repo.py         │    │ 对内暴露领域方法              │
│ quota_repo.py                │    │ 而非 SDK 原始 API             │
│                              │    │                               │
│ 职责：数据访问抽象           │    │                               │
│ 接收 AsyncSession 作为参数   │    │                               │
│ 不管理事务生命周期           │    │                               │
└──────────────────────────────┘    └───────────────────────────────┘
```

### 3.2 中间件 vs Depends 职责边界

| 层                           | 组件           | 职责                                             |
| ---------------------------- | -------------- | ------------------------------------------------ |
| **中间件**（基础设施级）     | CORS           | 跨域策略                                         |
|                              | RequestID      | 生成 trace_id，串联日志链路                      |
|                              | AccessLog      | 结构化访问日志（method, path, status, duration） |
|                              | RateLimit      | **粗粒度**反爬/反滥用（IP 级），不涉及业务配额   |
| **Depends**（业务级）        | JWT 验证       | `get_current_user`                               |
|                              | Workspace 隔离 | `get_current_workspace`                          |
|                              | DB Session     | `get_db`                                         |
| **QuotaService**（业务逻辑） | 业务限流       | 每用户 Agent Run 频率限制                        |
|                              | 配额扣减       | Token 消耗统计、月度额度检查                     |
|                              | 超限处理       | 抛 `QuotaExceededError` → 全局异常处理器 → 429   |

### 3.3 文件结构

```
backend/
├── main.py                          # FastAPI app 创建 + 中间件注册 + Router 挂载
│
├── api/                             # Router 层
│   ├── dependencies.py              # 依赖注入工厂
│   ├── schemas/                     # Pydantic 请求/响应模型（DTO）
│   │   ├── auth.py                  # TokenPayload, UserInfo
│   │   ├── agent.py                 # RunRequest, RunEvent, InterruptResponse
│   │   ├── document.py              # UploadInit, UploadConfirm, DocumentMeta
│   │   ├── workspace.py             # WorkspaceCreate, WorkspaceDetail, WorkspaceSummary
│   │   └── editor.py                # DraftSave, DraftLoad
│   └── routers/
│       ├── auth.py                  # GET /auth/me, PUT /auth/settings
│       ├── agent.py                 # Thread + Run 全生命周期
│       ├── document.py              # 文件上传 + 解析管理
│       ├── workspace.py             # Workspace CRUD + summary
│       └── editor.py                # 草稿保存/加载
│
├── services/                        # Service 层（业务编排）
│   ├── agent_service.py             # Agent 触发、Thread 管理、SSE 事件翻译、HITL
│   ├── document_service.py          # 预签名 URL、上传确认、解析重试、异步删除
│   ├── workspace_service.py         # Workspace CRUD + 聚合摘要
│   ├── editor_service.py            # 草稿自动保存 + 提交版查询
│   └── quota_service.py             # 配额检查、消耗记录、业务限流、用量统计
│
├── repositories/                    # Repository 层（数据访问抽象）
│   ├── base.py                      # BaseRepository[T] — 通用 CRUD 泛型基类
│   ├── user_repo.py                 # 用户数据访问
│   ├── workspace_repo.py            # Workspace + 成员关系查询
│   ├── document_repo.py             # 文档元数据 CRUD + 状态流转
│   ├── editor_repo.py               # 草稿读写
│   ├── run_snapshot_repo.py         # Run 输入快照 + 状态查询
│   └── quota_repo.py                # Token 消耗记录 + 统计查询
│
├── clients/                         # Client 层（外部系统连接器）
│   ├── langgraph_client.py          # langgraph-sdk HTTP Client 封装
│   ├── storage_client.py            # S3/MinIO（预签名 URL、head_object、删除）
│   └── auth_client.py               # 第三方 Auth JWT 验证 + 用户信息获取
│
├── core/                            # 全局核心组件（跨层共享）
│   ├── config.py                    # BaseSettings 配置加载
│   ├── database.py                  # SQLAlchemy async engine + session factory
│   ├── logger.py                    # 结构化日志（structlog, 支持 trace_id）
│   └── exceptions.py                # 自定义异常类型 + 全局异常处理器
│
└── models/                          # SQLAlchemy ORM 模型
    ├── user.py                      # 用户（同步自第三方 Auth）
    ├── workspace.py                 # Workspace + 成员关系
    ├── document.py                  # 文档元数据（与 RAG spec 对齐）
    ├── editor_draft.py              # 编辑器草稿
    ├── run_snapshot.py              # Run 输入快照
    └── quota_record.py              # Token 消耗记录
```

### 3.4 与 ARCHITECT.md 的关系说明

FastAPI BFF 范围内的模块限于上述文件结构。以下模块属于 LangGraph Server 侧，不在 BFF 范围内：

- `backend/agent/` — Agent 运行时（Supervisor + Workflows），由 LangGraph Server 加载
- `backend/services/sandbox_manager.py` — Docker 沙箱管理，由 Agent 节点直接调用
- `backend/services/parser_engine.py` — MinerU 解析封装，由 Celery Worker 调用
- `backend/services/rag_engine.py` — RAG 检索，由 Agent 节点调用
- `backend/workers/` — Celery 异步任务，独立 Worker 进程

---

## 四、API 路由设计

### 4.1 Auth — `/api/auth`

| 方法 | 路径             | 说明                           | 备注                           |
| ---- | ---------------- | ------------------------------ | ------------------------------ |
| GET  | `/auth/me`       | 获取当前用户信息               | JWT 解析 → 查/同步本地 user 表 |
| PUT  | `/auth/settings` | 更新用户设置（学科偏好、BYOK） | 存本地 DB                      |

> 注册/登录/密码重置全部走第三方 Auth 服务的前端 SDK，不经过 FastAPI。FastAPI 只验证 JWT。

### 4.2 Workspace — `/api/workspaces`

| 方法   | 路径                       | 说明                                                  |
| ------ | -------------------------- | ----------------------------------------------------- |
| POST   | `/workspaces`              | 创建 Workspace（课题空间）                            |
| GET    | `/workspaces`              | 获取当前用户的所有 Workspace                          |
| GET    | `/workspaces/{id}`         | 获取 Workspace 详情                                   |
| GET    | `/workspaces/{id}/summary` | 聚合摘要（最近 thread、文档数、处理中任务、最近产物） |
| PUT    | `/workspaces/{id}`         | 更新 Workspace 设置                                   |
| DELETE | `/workspaces/{id}`         | 删除 Workspace                                        |

### 4.3 Document — `/api/documents`

| 方法   | 路径                        | 说明                                                      |
| ------ | --------------------------- | --------------------------------------------------------- |
| POST   | `/documents/upload-url`     | 生成 S3 预签名上传 URL + 创建 document 记录               |
| POST   | `/documents/confirm`        | 前端上传完成确认 → S3 存在性校验 → 触发 Celery 解析       |
| GET    | `/documents`                | 获取当前 Workspace 下的文档列表（支持 parse_status 过滤） |
| GET    | `/documents/{id}`           | 获取文档详情（含 parse_status）                           |
| GET    | `/documents/{id}/artifacts` | 查询解析产物（按类型分组：段落/表格/图表/公式）           |
| POST   | `/documents/{id}/retry`     | 重试失败的解析（状态守卫：仅 failed → pending）           |
| DELETE | `/documents/{id}`           | 标记 deleting → 异步 Celery 清理 S3 + RAG 数据            |

#### 文件上传时序

```
前端                    FastAPI BFF                   S3/MinIO          Celery
 │                         │                            │                │
 │ POST /upload-url        │                            │                │
 │ {filename, content_type}│                            │                │
 │────────────────────────►│ 创建 document (uploading)  │                │
 │                         │ generate_presigned_url()   │                │
 │                         │───────────────────────────►│                │
 │   {upload_url, doc_id}  │                            │                │
 │◄────────────────────────│                            │                │
 │                         │                            │                │
 │ PUT upload_url (binary) │                            │                │
 │─────────────────────────┼───────────────────────────►│                │
 │         200 OK          │                            │                │
 │◄────────────────────────┼────────────────────────────│                │
 │                         │                            │                │
 │ POST /confirm {doc_id}  │                            │                │
 │────────────────────────►│ head_object() 校验文件存在 │                │
 │                         │───────────────────────────►│                │
 │                         │ 更新状态 → pending         │                │
 │                         │ dispatch ingestion task    │                │
 │                         │───────────────────────────────────────────►│
 │         202 Accepted    │                            │                │
 │◄────────────────────────│                            │                │
```

### 4.4 Agent — `/api/agent`

| 方法   | 路径                                       | 说明                                                 |
| ------ | ------------------------------------------ | ---------------------------------------------------- |
| POST   | `/agent/threads`                           | 创建新 Thread（本地先占位 → LangGraph 创建 → 回写）  |
| GET    | `/agent/threads`                           | 获取当前 Workspace 下的 Thread 列表                  |
| GET    | `/agent/threads/{id}`                      | 获取 Thread 详情                                     |
| DELETE | `/agent/threads/{id}`                      | 删除 Thread                                          |
| POST   | `/agent/threads/{id}/runs`                 | 触发 Agent Run（存快照 → 配额检查 → 转发 LangGraph） |
| GET    | `/agent/threads/{id}/runs`                 | 获取 Thread 下的 Run 列表（只返回根 Run）            |
| GET    | `/agent/threads/{id}/runs/{run_id}`        | 获取 Run 详情（含子 Run 链、耗时、token 消耗）       |
| GET    | `/agent/threads/{id}/runs/{run_id}/stream` | SSE 流式接收翻译后的执行事件                         |
| POST   | `/agent/threads/{id}/runs/{run_id}/resume` | HITL 恢复 → 创建新 Run → 返回新 stream URL           |
| POST   | `/agent/threads/{id}/runs/{run_id}/cancel` | 取消/终止正在执行的 Run                              |

#### 触发 Run 请求体

```python
class RunRequest(BaseModel):
    message: str                              # 用户指令
    editor_content: str | None = None         # 用户显式提交的编辑器内容
    attachment_ids: list[UUID] | None = None  # 关联的文档 ID 列表
```

#### HITL Resume 响应

```python
class ResumeResponse(BaseModel):
    resumed_run_id: UUID       # 新建的 Run ID
    parent_run_id: UUID        # 被恢复的 Run ID
    stream_url: str            # 新 Run 的 SSE stream 路径
```

### 4.5 Editor — `/api/editor`

| 方法 | 路径                        | 说明                                               |
| ---- | --------------------------- | -------------------------------------------------- |
| PUT  | `/editor/draft`             | 自动保存草稿（防抖调用，per thread_id 覆盖式写入） |
| GET  | `/editor/draft/{thread_id}` | 加载某 Thread 对应的最新草稿                       |

> 编辑器向 Agent 提交内容不走独立 API，嵌入在 `POST /agent/threads/{id}/runs` 的 `editor_content` 字段中。

---

## 五、依赖注入

### 5.1 依赖链

```python
# --- 基础设施依赖 ---

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """每请求一个 DB session，请求结束自动关闭"""

def get_settings() -> Settings:
    """全局配置单例（lru_cache）"""

# --- 认证依赖 ---

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_client: AuthClient = Depends(get_auth_client),
    user_repo: UserRepo = Depends(get_user_repo),
) -> User:
    """验证 JWT → 查/同步本地用户 → 返回 User"""

# --- 租户隔离依赖 ---

async def get_current_workspace(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepo = Depends(get_workspace_repo),
) -> Workspace:
    """验证用户对该 Workspace 的访问权限 → 返回 Workspace"""

# --- Repository 依赖 ---

async def get_document_repo(db: AsyncSession = Depends(get_db)) -> DocumentRepo:
    return DocumentRepo(db)

# ... 其他 repo 同理

# --- Client 依赖 ---

def get_langgraph_client(settings: Settings = Depends(get_settings)) -> LangGraphClient:
    return LangGraphClient(base_url=settings.langgraph_server_url)

def get_storage_client(settings: Settings = Depends(get_settings)) -> StorageClient:
    return StorageClient(endpoint=settings.s3_endpoint, ...)

# --- Service 依赖（组装 repo + client）---

async def get_agent_service(
    lg_client: LangGraphClient = Depends(get_langgraph_client),
    workspace_repo: WorkspaceRepo = Depends(get_workspace_repo),
    run_snapshot_repo: RunSnapshotRepo = Depends(get_run_snapshot_repo),
    quota_service: QuotaService = Depends(get_quota_service),
) -> AgentService:
    return AgentService(lg_client, workspace_repo, run_snapshot_repo, quota_service)
```

### 5.2 依赖层次图

```
Router
  └─ Depends(get_agent_service)
       ├─ Depends(get_langgraph_client)
       │    └─ Depends(get_settings)
       ├─ Depends(get_workspace_repo)
       │    └─ Depends(get_db)
       ├─ Depends(get_run_snapshot_repo)
       │    └─ Depends(get_db)          ← FastAPI 自动去重，同一个 session
       └─ Depends(get_quota_service)
            └─ Depends(get_quota_repo)
                 └─ Depends(get_db)     ← 同上
```

---

## 六、异常处理

### 6.1 异常类型层次

```python
class AppError(Exception):
    """业务异常基类"""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"

class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"

class QuotaExceededError(AppError):
    status_code = 429
    error_code = "QUOTA_EXCEEDED"

class LangGraphUnavailableError(AppError):
    status_code = 502
    error_code = "AGENT_UNAVAILABLE"
    message = "Agent service is temporarily unavailable"

class ParseRetryError(AppError):
    status_code = 409
    error_code = "PARSE_IN_PROGRESS"
    message = "Document is already being parsed"

class UploadNotFoundError(AppError):
    status_code = 400
    error_code = "UPLOAD_NOT_FOUND"
    message = "File not found in storage after upload"

class InvalidStateTransitionError(AppError):
    status_code = 409
    error_code = "INVALID_STATE"
    message = "Invalid state transition for this resource"
```

### 6.2 全局异常处理器

```python
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail": exc.message,
            "trace_id": request.state.trace_id,
        },
    )
```

### 6.3 响应格式示例

正常响应 — 直接返回业务数据，无包装层：

```json
// GET /workspaces → 200
[
  { "id": "...", "name": "Transformer 研究", "created_at": "..." },
  { "id": "...", "name": "药物发现", "created_at": "..." }
]
```

异常响应 — 统一 `error_code` + `detail` + `trace_id`：

```json
// POST /agent/threads/{id}/runs → 429
{
  "error_code": "QUOTA_EXCEEDED",
  "detail": "Monthly token quota exceeded for this workspace",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 七、BFF 侧数据模型

BFF 只管理与业务控制面相关的表。RAG 相关的内容表（paragraphs、tables 等）由 RAG Pipeline 管理，此处不重复。

### 7.1 `users` — 用户（同步自第三方 Auth）

| 字段         | 类型        | 说明                                  |
| ------------ | ----------- | ------------------------------------- |
| id           | UUID        | 主键                                  |
| external_id  | TEXT        | 第三方 Auth 的用户 ID，UNIQUE         |
| email        | TEXT        | 邮箱                                  |
| display_name | TEXT        | 显示名                                |
| settings     | JSONB       | 用户设置（学科偏好、BYOK API Key 等） |
| created_at   | TIMESTAMPTZ | 首次同步时间                          |
| updated_at   | TIMESTAMPTZ | 最近更新                              |

### 7.2 `workspaces` — 课题空间

| 字段       | 类型        | 说明                                    |
| ---------- | ----------- | --------------------------------------- |
| id         | UUID        | 主键                                    |
| owner_id   | UUID        | FK → users                              |
| name       | TEXT        | 空间名称                                |
| discipline | TEXT        | 学科领域（用于 Supervisor prompt 切换） |
| is_deleted | BOOL        | 软删除标记                              |
| created_at | TIMESTAMPTZ | 创建时间                                |

### 7.3 `threads` — 对话 Thread（本地镜像）

| 字段                | 类型        | 说明                              |
| ------------------- | ----------- | --------------------------------- |
| id                  | UUID        | 主键，与 LangGraph thread_id 一致 |
| workspace_id        | UUID        | FK → workspaces                   |
| title               | TEXT        | 对话标题（自动或用户修改）        |
| status              | ENUM        | `creating / active / failed`      |
| langgraph_thread_id | UUID        | LangGraph 侧的 Thread ID          |
| created_at          | TIMESTAMPTZ | 创建时间                          |

### 7.4 `run_snapshots` — Run 输入快照

| 字段           | 类型        | 说明                                                     |
| -------------- | ----------- | -------------------------------------------------------- |
| id             | UUID        | 主键                                                     |
| run_id         | UUID        | 对应 LangGraph 的 run_id                                 |
| thread_id      | UUID        | FK → threads                                             |
| parent_run_id  | UUID        | 父 Run ID（HITL resume 链），可为空                      |
| user_message   | TEXT        | 用户原始指令                                             |
| editor_content | TEXT        | 提交时的编辑器内容快照，可为空                           |
| attachment_ids | UUID[]      | 关联文档 ID 列表                                         |
| status         | ENUM        | `running / completed / failed / cancelled / interrupted` |
| tokens_used    | INT         | Run 结束后回填                                           |
| created_at     | TIMESTAMPTZ | 触发时间                                                 |
| completed_at   | TIMESTAMPTZ | 结束时间，可为空                                         |

### 7.5 `editor_drafts` — 编辑器草稿

| 字段       | 类型        | 说明                                   |
| ---------- | ----------- | -------------------------------------- |
| id         | UUID        | 主键                                   |
| thread_id  | UUID        | FK → threads，UNIQUE（每 Thread 一条） |
| content    | TEXT        | Tiptap JSON 或 Markdown 内容           |
| updated_at | TIMESTAMPTZ | 最后保存时间                           |

### 7.6 `quota_records` — Token 消耗记录

| 字段          | 类型        | 说明               |
| ------------- | ----------- | ------------------ |
| id            | UUID        | 主键               |
| workspace_id  | UUID        | FK → workspaces    |
| run_id        | UUID        | FK → run_snapshots |
| model_name    | TEXT        | 使用的模型名       |
| input_tokens  | INT         | 输入 token 数      |
| output_tokens | INT         | 输出 token 数      |
| created_at    | TIMESTAMPTZ | 记录时间           |

### 7.7 文档状态机

```
                    ┌──────── upload_expired (超时未确认)
                    │
 uploading ────► pending ────► parsing ────► completed
     │              ↑             │
     │              │             ▼
     │              └────────  failed
     │            (retry_parse)
     │
     └──► upload_failed (S3 上传异常)

 任意状态 ──► deleting ──► deleted (软删除)
```

状态流转用显式守卫函数，非法转换抛 `InvalidStateTransitionError(409)`。

---

## 八、Agent 交互核心设计

### 8.1 AgentService 职责

```
AgentService
├── create_thread()         创建 Thread（本地先占位 → LangGraph → 回写，含失败补偿）
├── trigger_run()           触发 Run（存快照 → 配额检查 → 转发 LangGraph）
├── stream_run_events()     SSE 事件翻译（纯翻译 + 推送 + seq 计数，不做业务计算）
├── on_run_complete()       Run 结束回调（配额扣减、状态回写，与 stream 分离）
├── resume_run()            HITL 恢复（创建新 Run，建立 parent_run_id 链接）
├── cancel_run()            取消 Run
├── get_thread_runs()       查询 Run 列表（只返回根 Run）
└── get_run_detail()        查询 Run 详情（含子 Run 链）
```

### 8.2 SSE 事件翻译机制

#### 翻译规则表

```python
EVENT_MAPPING: dict[str, str] = {
    "events/metadata":              "run_start",
    "events/on_chain_start":        "node_start",
    "events/on_chain_end":          "node_end",
    "events/on_chat_model_stream":  "token",
    "events/on_tool_start":         "tool_call",
    "events/on_tool_end":           "tool_result",
    "__interrupt__":                 "interrupt",
    "error":                        "error",
}

# 每种事件类型有独立的 data 提取函数
# 无法映射的事件类型 → 静默跳过
# 新增事件类型 → 加一行映射 + 对应的提取函数
```

#### 统一事件模型

```python
class RunEvent(BaseModel):
    # --- 协议层（每个事件必有）---
    seq: int                              # 单调递增序列号，用于断线重连排序
    run_id: UUID                          # 当前 Run ID
    thread_id: UUID                       # 所属 Thread ID
    timestamp: datetime                   # 事件产生时间

    # --- 业务层（按 event_type 变化）---
    event_type: Literal[
        "run_start", "node_start", "node_end",
        "token", "tool_call", "tool_result",
        "interrupt", "run_end", "error",
    ]
    node_name: str | None = None          # 当前节点（如 "discovery.search"）
    data: dict | None = None              # 事件负载
```

#### 断线重连

前端断线重连带 `Last-Event-ID`（= 最后收到的 `seq`），FastAPI 从该 seq 之后重播事件。事件缓冲存 Redis（key = `run:{run_id}:events`，TTL = Run 存活期）。

#### stream_run_events() 职责边界

```
stream_run_events()  ← 只做：读 LangGraph stream → 翻译 → 推送 → seq 计数
                       不做：配额扣减、状态更新、DB 写入

Run 结束时的业务计算由 on_run_complete() 负责：
  1. quota_service.record_usage(run_id, tokens_used)
  2. run_snapshot_repo.update_status(run_id, "completed")
  3. 推送最后一个 run_end 事件给前端（携带 tokens_used）
```

### 8.3 SSE 翻译时序

```
LangGraph Server                    AgentService                        前端
(langgraph-sdk stream)              (stream_run_events)                 (EventSource)
      │                                  │                                  │
      │ events/metadata                  │                                  │
      │─────────────────────────────────►│ seq=1, RunEvent(run_start)       │
      │                                  │─────────────────────────────────►│
      │                                  │                                  │
      │ events/on_chain_start            │                                  │
      │ {name: "discovery.search"}       │                                  │
      │─────────────────────────────────►│ seq=2, RunEvent(node_start,      │
      │                                  │   node_name="discovery.search")  │
      │                                  │─────────────────────────────────►│
      │                                  │                                  │
      │ events/on_chat_model_stream      │                                  │
      │ {chunk: "根据检索结果..."}        │                                  │
      │─────────────────────────────────►│ seq=3, RunEvent(token)           │
      │                                  │─────────────────────────────────►│
      │                                  │                                  │
      │ __interrupt__                    │                                  │
      │ {value: {code: "...",            │                                  │
      │  action: "confirm_execute"}}     │                                  │
      │─────────────────────────────────►│ seq=N, RunEvent(interrupt)       │
      │                                  │─────────────────────────────────►│
      │                                  │                                  │
      │ (stream 结束)                    │ on_run_complete() 回调           │
      │─────────────────────────────────►│ → 配额扣减 + 状态回写           │
      │                                  │ seq=N+1, RunEvent(run_end)       │
      │                                  │─────────────────────────────────►│
```

### 8.4 Thread 双写与失败补偿

| 存储位置             | 存什么                                    | 为什么                       |
| -------------------- | ----------------------------------------- | ---------------------------- |
| **LangGraph Server** | Thread 完整状态 + Checkpoint              | Agent 运行时需要             |
| **本地 PostgreSQL**  | thread_id + workspace_id + title + status | Workspace 隔离查询、权限校验 |

#### create_thread() 流程

```
1. 写本地 DB（status = "creating"）              ← 先占位
2. 调用 LangGraph 创建 Thread
3. 成功 → 更新本地 DB（status = "active", langgraph_thread_id = ...）
4. LangGraph 失败 → 更新本地 DB（status = "failed"）→ 抛异常
5. 步骤 3 本地 DB 写入失败 → 日志告警，LangGraph 侧成为孤儿

孤儿补偿：后台定时任务扫描 status = "creating" 且超过 5 分钟的记录
  → 尝试删除 LangGraph 侧对应 Thread
  → 无论成功失败，标记本地记录为 "failed"
```

核心原则：本地 DB 先写占位，LangGraph 是被协调方。不做分布式事务，用最终一致 + 后台补偿。

### 8.5 HITL 恢复流程

```
前端                         FastAPI BFF                    LangGraph Server
 │                              │                               │
 │  收到 interrupt 事件         │                               │
 │  展示确认卡片                │                               │
 │                              │                               │
 │ POST /runs/{id}/resume       │                               │
 │ { action: "approve" }        │                               │
 │─────────────────────────────►│                               │
 │                              │ quota_service.check()         │
 │                              │ 创建 run_snapshot             │
 │                              │   (parent_run_id = old_id)    │
 │                              │ client.runs.create(           │
 │                              │   thread_id,                  │
 │                              │   command=Command(             │
 │                              │     resume={action:"approve"} │
 │                              │   )                           │
 │                              │ )                             │
 │                              │──────────────────────────────►│
 │  202 Accepted                │                               │ Agent 继续执行
 │  {resumed_run_id,            │                               │
 │   parent_run_id,             │                               │
 │   stream_url}                │                               │
 │◄─────────────────────────────│                               │
 │                              │                               │
 │ GET /runs/{new_id}/stream    │                               │
 │─────────────────────────────►│  连接新 Run 的 SSE stream     │
```

#### Run 身份关系模型

```
Thread
 └── Run A (initial, status=interrupted)
      └── Run B (resume of A, parent_run_id=A)
           └── Run C (resume of B, parent_run_id=B)

查询规则：
- GET /threads/{id}/runs      → 只返回根 Run（parent_run_id IS NULL）
- GET /runs/{id}              → 返回详情 + 展开子 Run 链
```

---

## 九、Service 层详细设计

### 9.1 DocumentService

```
DocumentService
├── generate_upload_url()     生成预签名 URL + 创建 document 记录(status=uploading)
├── confirm_upload()          S3 head_object 校验 → 更新状态 → 投递 Celery 解析
├── retry_parse()             状态守卫(仅 failed→pending) → 重投 Celery
├── get_artifacts()           查询解析产物（按类型分组）
├── list_documents()          Workspace 下文档列表（支持 parse_status 过滤）
└── delete_document()         标记 deleting → 异步 Celery 清理
```

#### confirm_upload() 逻辑

```python
async def confirm_upload(doc_id: UUID) -> DocumentMeta:
    doc = await document_repo.get_by_id(doc_id)
    assert_status(doc, expected="uploading")

    # S3 存在性校验
    exists = await storage_client.head_object(doc.file_path)
    if not exists:
        await document_repo.update_status(doc_id, "upload_failed")
        raise UploadNotFoundError()

    await document_repo.update_status(doc_id, "pending")
    await celery_app.send_task("ingestion.parse", args=[str(doc_id)])
    return doc
```

#### delete_document() 逻辑

```python
async def delete_document(doc_id: UUID) -> None:
    doc = await document_repo.get_by_id(doc_id)
    # 立即标记 deleting，前端不再展示
    await document_repo.update_status(doc_id, "deleting")
    # 重活异步投递
    await celery_app.send_task("cleanup.delete_document_assets", args=[str(doc_id)])
    # Celery 任务内部：删 S3 → 删 RAG 分表 → 标记 deleted
    # 失败重试 3 次，仍失败标记 delete_failed + 告警
```

### 9.2 EditorService

```
EditorService
├── save_draft()              防抖保存草稿（per thread_id 覆盖式 UPSERT）
├── load_draft()              加载最新草稿
└── get_submitted_version()   查询某次 Run 提交时的编辑器快照（从 run_snapshots 读）
```

草稿 vs 提交版区别：
- **草稿**（`editor_drafts` 表）：自动保存，频繁覆盖，per thread 一条
- **提交版**：存在 `run_snapshots.editor_content` 字段中，随 Run 创建固化，不可变

### 9.3 WorkspaceService

```
WorkspaceService
├── create_workspace()
├── get_workspace_summary()   聚合摘要（并行查询，避免 N+1）
├── list_workspaces()
├── update_workspace()
└── delete_workspace()        软删除 + 级联标记子资源
```

#### get_workspace_summary() 实现

```python
async def get_workspace_summary(workspace_id: UUID) -> WorkspaceSummary:
    recent_threads, doc_stats, active_tasks, recent_artifacts = await gather(
        thread_repo.list_recent(workspace_id, limit=5),
        document_repo.count_by_status(workspace_id),
        run_snapshot_repo.count_active(workspace_id),
        run_snapshot_repo.list_recent_completed(workspace_id, limit=5),
    )
    return WorkspaceSummary(
        recent_threads=recent_threads,
        total_documents=doc_stats.total,
        parsing_documents=doc_stats.parsing,
        active_runs=active_tasks,
        recent_artifacts=recent_artifacts,
    )
```

### 9.4 QuotaService

```
QuotaService
├── check_quota()             触发 Run 前检查额度 → 不足抛 QuotaExceededError
├── check_rate_limit()        业务级频率限制（如每用户每分钟 N 次 Run）
├── record_usage()            Run 结束后记录 token 消耗（on_run_complete 调用）
└── get_usage_stats()         按 Workspace 统计消耗（供设置页展示）
```

---

## 十、技术选型汇总

| 组件           | 选择                      | 理由                                  |
| -------------- | ------------------------- | ------------------------------------- |
| Web 框架       | FastAPI                   | 异步原生，Pydantic 类型安全，团队经验 |
| ORM            | SQLAlchemy 2.0 (async)    | 成熟稳定，原生 async session          |
| 数据校验       | Pydantic V2               | FastAPI 原生支持，高性能              |
| JWT 验证       | 第三方 Auth SDK + PyJWT   | 只验证不签发                          |
| 对象存储       | boto3 (S3) / minio-py     | S3 兼容 API，云端/私有化统一          |
| LangGraph 通信 | langgraph-sdk HTTP Client | 底层控制，显式生命周期管理            |
| 异步任务       | Celery + Redis            | 与架构文档一致                        |
| 结构化日志     | structlog                 | 支持 trace_id 串联，JSON 输出         |
| 限流           | Redis + 令牌桶            | 粗粒度中间件 + 业务级 QuotaService    |
| SSE 事件缓冲   | Redis (TTL key)           | 断线重连事件重播                      |

