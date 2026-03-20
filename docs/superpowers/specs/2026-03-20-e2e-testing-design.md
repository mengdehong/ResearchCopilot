# E2E 测试与前后端集成验证设计规格

> **目标**：为 Research Copilot 建立 API 级集成测试体系，覆盖全部后端模块，验证真实数据库/缓存/存储环境下的 API 契约与数据流正确性。
> **日期**：2026-03-20

---

## 一、需求概述

### 核心目标
- 对全部 6 个 API Router（health/auth/workspace/document/editor/agent）做端到端 API 验证
- 基于真实基础设施（PostgreSQL + Redis + MinIO），Mock 外部服务（LLM/OAuth/Email）
- 共享种子数据集，session 级 fixture 一次创建、所有测试共享
- 可在本地和 CI 中快速运行

### 测试边界

| 层级                  | 真实运行      | Mock                  |
| --------------------- | ------------- | --------------------- |
| FastAPI App           | ✅ 进程内      | —                     |
| PostgreSQL (pgvector) | ✅ Docker 容器 | —                     |
| Redis                 | ✅ Docker 容器 | —                     |
| MinIO                 | ✅ Docker 容器 | —                     |
| LangGraph Client      | —             | ✅ MockLangGraphClient |
| OAuth Provider        | —             | ✅ MockOAuthProvider   |
| Email Service         | —             | ✅ MockEmailService    |

---

## 二、整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                     pytest 进程                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  httpx.AsyncClient (ASGITransport)                      │ │
│  │       ↕ ASGI 协议（无网络开销）                          │ │
│  │  FastAPI app (in-process, 完整 lifespan)                │ │
│  └──────────────┬──────────────┬──────────────┬────────────┘ │
│                 │              │              │              │
│        ┌────────▼───┐  ┌──────▼─────┐  ┌────▼──────┐       │
│        │ PostgreSQL │  │   Redis    │  │   MinIO   │       │
│        │  (Docker)  │  │  (Docker)  │  │  (Docker) │       │
│        └────────────┘  └────────────┘  └───────────┘       │
│                                                              │
│  dependency_overrides:                                       │
│    _get_lg_client  → MockLangGraphClient                    │
│    OAuthProvider   → MockOAuthProvider                      │
│    EmailService    → MockEmailService                       │
└──────────────────────────────────────────────────────────────┘
```

### 与现有测试体系的关系

```
tests/
├── unit/           ← 纯 mock，无外部依赖，pytest -m unit
├── integration/    ← 数据库级别（repository 层），pytest -m integration
└── e2e/            ← API 级别（本设计），pytest -m e2e
                      需要 make infra 启动 PG/Redis/MinIO
```

---

## 三、Fixture 设计

### 3.1 层级结构

```python
# ── session 级（每次 pytest 运行只执行一次）──

test_app        → 创建 FastAPI app + 注入 dependency_overrides + 执行 lifespan
test_db_engine  → 创建 async engine，连接测试数据库
                  运行 alembic upgrade head 初始化 schema

test_client     → httpx.AsyncClient(transport=ASGITransport(app))

seed_data       → 在数据库中创建完整种子数据集
                  返回 SeedData dataclass（包含所有实体 ID 和 token）

auth_headers    → {"Authorization": "Bearer <access_token>"}

# ── function 级（每个测试函数独立）──

独立创建的业务数据（如需要）
```

### 3.2 SeedData 结构

```python
@dataclass(frozen=True)
class SeedData:
    """Session 级种子数据，所有测试共享。"""
    # 用户
    user_id: uuid.UUID
    user_email: str
    access_token: str

    # Workspace
    workspace_id: uuid.UUID           # 主 workspace
    workspace_id_other: uuid.UUID     # 权限隔离测试用

    # Document
    document_id: uuid.UUID            # 已创建的文档（状态 pending）

    # Agent Thread
    thread_id: uuid.UUID              # 已创建的 thread

    # Editor Draft
    draft_thread_id: uuid.UUID        # 已关联草稿的 thread
```

### 3.3 Mock 对象设计

```python
class MockLangGraphClient:
    """Mock LangGraph 客户端，返回固定 run 结果。"""
    async def create_thread(self) -> dict: ...
    async def create_run(self, thread_id, input) -> dict: ...
    async def stream_events(self, thread_id, run_id) -> AsyncIterator: ...

class MockOAuthProvider:
    """Mock OAuth，exchange_code 直接返回预设用户信息。"""
    provider_name: str = "github"
    def get_authorize_url(self, state, redirect_uri) -> str: ...
    async def exchange_code(self, code, redirect_uri) -> OAuthUserInfo: ...

class MockEmailService:
    """Mock 邮件服务，记录调用参数供断言。"""
    sent_emails: list[tuple[str, str]]  # [(to, token), ...]
    async def send_verification_email(self, to, token) -> None: ...
    async def send_password_reset_email(self, to, token) -> None: ...
```

---

## 四、测试用例覆盖矩阵

### 4.1 `test_auth_e2e.py` — 认证模块

#### 注册流程

| 用例                | 端点                      | 输入                             | 预期                                               |
| ------------------- | ------------------------- | -------------------------------- | -------------------------------------------------- |
| 正常注册            | `POST /api/auth/register` | 合法 email + 密码 + display_name | 201 + "验证邮件已发送" + MockEmailService 记录调用 |
| 重复邮箱            | `POST /api/auth/register` | 已存在的 email                   | 409 Conflict                                       |
| 弱密码（短）        | `POST /api/auth/register` | password="123"                   | 422                                                |
| 弱密码（纯字母）    | `POST /api/auth/register` | password="abcdefgh"              | 422                                                |
| 邮箱已被 OAuth 注册 | `POST /api/auth/register` | OAuth 用户的 email               | 409 + 提示用 OAuth 登录                            |

#### 邮箱验证

| 用例       | 端点                          | 输入                           | 预期                      |
| ---------- | ----------------------------- | ------------------------------ | ------------------------- |
| 有效 token | `POST /api/auth/verify-email` | 合法 JWT(purpose=email_verify) | 200 + email_verified=true |
| 过期 token | `POST /api/auth/verify-email` | 过期 JWT                       | 400                       |
| 无效 token | `POST /api/auth/verify-email` | 随机字符串                     | 400                       |

#### 登录流程

| 用例         | 端点                   | 输入             | 预期                                                     |
| ------------ | ---------------------- | ---------------- | -------------------------------------------------------- |
| 正确凭据     | `POST /api/auth/login` | email + password | 200 + access_token + Set-Cookie(refresh_token, httpOnly) |
| 错误密码     | `POST /api/auth/login` | email + 错误密码 | 401                                                      |
| 邮箱未验证   | `POST /api/auth/login` | 未验证用户       | 403                                                      |
| 不存在的邮箱 | `POST /api/auth/login` | 不存在邮箱       | 401                                                      |

#### Token 刷新

| 用例                | 端点                     | 输入                  | 预期                  |
| ------------------- | ------------------------ | --------------------- | --------------------- |
| 有效 refresh cookie | `POST /api/auth/refresh` | 合法 Cookie           | 200 + 新 access_token |
| 无 cookie           | `POST /api/auth/refresh` | 无 Cookie             | 401                   |
| 已吊销的 token      | `POST /api/auth/refresh` | revoked=true 的 token | 401                   |

#### 登出

| 用例     | 端点                    | 输入        | 预期                                 |
| -------- | ----------------------- | ----------- | ------------------------------------ |
| 正常登出 | `POST /api/auth/logout` | 合法 Cookie | 204 + Clear-Cookie + DB 标记 revoked |

#### 密码重置

| 用例         | 端点                             | 输入                | 预期                            |
| ------------ | -------------------------------- | ------------------- | ------------------------------- |
| 存在的邮箱   | `POST /api/auth/forgot-password` | 已注册 email        | 200 + MockEmailService 记录调用 |
| 不存在的邮箱 | `POST /api/auth/forgot-password` | 不存在 email        | 200（防枚举）                   |
| 有效重置     | `POST /api/auth/reset-password`  | 合法 token + 新密码 | 200 + 旧 refresh_token 全部吊销 |
| 无效 token   | `POST /api/auth/reset-password`  | 过期/无效 token     | 400                             |

#### OAuth 流程

| 用例             | 端点                                   | 输入                           | 预期                                 |
| ---------------- | -------------------------------------- | ------------------------------ | ------------------------------------ |
| 发起授权         | `GET /api/auth/oauth/github/authorize` | —                              | 302 + Location 含 github.com         |
| 新用户回调       | `GET /api/auth/oauth/github/callback`  | code + state                   | 302 到前端 + Set-Cookie + 用户已创建 |
| 已有用户自动关联 | callback                               | 同 email、email_verified=true  | 302 + 关联到已有用户                 |
| 拒绝关联         | callback                               | 同 email、email_verified=false | 拒绝 + 提示先验证邮箱                |

#### 已有端点

| 用例         | 端点                     | 输入          | 预期                    |
| ------------ | ------------------------ | ------------- | ----------------------- |
| 获取用户信息 | `GET /api/auth/me`       | 合法 token    | 200 + UserInfo          |
| 无 token     | `GET /api/auth/me`       | 无 header     | 401                     |
| 过期 token   | `GET /api/auth/me`       | 过期 JWT      | 401                     |
| 更新设置     | `PUT /api/auth/settings` | settings dict | 200 + 更新后的 UserInfo |

---

### 4.2 `test_workspace_e2e.py` — Workspace 模块

| 用例           | 端点                               | 输入              | 预期                            |
| -------------- | ---------------------------------- | ----------------- | ------------------------------- |
| 创建 workspace | `POST /api/workspaces`             | name + discipline | 201 + WorkspaceDetail           |
| 列表 workspace | `GET /api/workspaces`              | —                 | 200 + 仅自己的 workspace        |
| 获取详情       | `GET /api/workspaces/{id}`         | 有效 ID           | 200 + WorkspaceDetail           |
| 获取不存在     | `GET /api/workspaces/{id}`         | 随机 UUID         | 404                             |
| 更新 workspace | `PUT /api/workspaces/{id}`         | 新 name           | 200 + 更新后数据                |
| 软删除         | `DELETE /api/workspaces/{id}`      | 有效 ID           | 204                             |
| 删除后再获取   | `GET /api/workspaces/{id}`         | 已删除 ID         | 404                             |
| 工作区摘要     | `GET /api/workspaces/{id}/summary` | 有效 ID           | 200 + document_count + 状态统计 |

---

### 4.3 `test_document_e2e.py` — 文档管理模块

| 用例             | 端点                                                        | 输入                                | 预期                                         |
| ---------------- | ----------------------------------------------------------- | ----------------------------------- | -------------------------------------------- |
| 获取上传 URL     | `POST /api/documents/upload-url`                            | workspace_id + title + content_type | 201 + document_id + upload_url + storage_key |
| 不存在 workspace | `POST /api/documents/upload-url`                            | 无效 workspace_id                   | 404                                          |
| 确认上传         | `POST /api/documents/confirm`                               | document_id                         | 200 + DocumentMeta(status=pending)           |
| 列表文档         | `GET /api/documents?workspace_id=xxx`                       | workspace_id                        | 200 + DocumentMeta[]                         |
| 按状态过滤       | `GET /api/documents?workspace_id=xxx&status_filter=pending` | 过滤参数                            | 200 + 仅 pending 文档                        |
| 获取文档详情     | `GET /api/documents/{id}`                                   | 有效 ID                             | 200 + DocumentMeta                           |
| 获取解析状态     | `GET /api/documents/{id}/status`                            | 有效 ID                             | 200 + DocumentStatus                         |
| 获取解析产物     | `GET /api/documents/{id}/artifacts`                         | 有效 ID                             | 200 + artifacts 数组                         |
| 重试解析         | `POST /api/documents/{id}/retry`                            | 有效 ID                             | 200 + DocumentMeta                           |
| 删除文档         | `DELETE /api/documents/{id}`                                | 有效 ID                             | 204                                          |
| 删除不存在文档   | `DELETE /api/documents/{id}`                                | 随机 UUID                           | 404                                          |

---

### 4.4 `test_agent_e2e.py` — Agent 交互模块

| 用例          | 端点                                                | 输入                 | 预期                                        |
| ------------- | --------------------------------------------------- | -------------------- | ------------------------------------------- |
| 创建 thread   | `POST /api/agent/threads?workspace_id=xxx`          | workspace_id + title | 200 + thread_id                             |
| 列表 threads  | `GET /api/agent/threads?workspace_id=xxx`           | workspace_id         | 200 + ThreadDetail[]                        |
| 获取 thread   | `GET /api/agent/threads/{id}`                       | thread_id            | 200 + ThreadDetail                          |
| 删除 thread   | `DELETE /api/agent/threads/{id}`                    | thread_id            | 204                                         |
| 触发 run      | `POST /api/agent/threads/{id}/runs`                 | message 内容         | 200 + run_id（MockLangGraphClient 返回）    |
| 列表 runs     | `GET /api/agent/threads/{id}/runs`                  | thread_id            | 200 + RunDetail[]                           |
| 获取 run 详情 | `GET /api/agent/threads/{id}/runs/{run_id}`         | thread_id + run_id   | 200 + RunDetail                             |
| SSE 事件流    | `GET /api/agent/threads/{id}/runs/{run_id}/events`  | thread_id + run_id   | 200 + text/event-stream + 可解析的 SSE 事件 |
| 恢复暂停 run  | `POST /api/agent/threads/{id}/runs/{run_id}/resume` | InterruptResponse    | 200（MockLangGraphClient 验证调用参数）     |
| 取消 run      | `POST /api/agent/threads/{id}/runs/{run_id}/cancel` | —                    | 200                                         |
| 权限校验      | `GET /api/agent/threads/{id}`                       | 他人的 thread_id     | 403 或 404                                  |

---

### 4.5 `test_editor_e2e.py` — 编辑器模块

| 用例          | 端点                                | 输入                     | 预期                                     |
| ------------- | ----------------------------------- | ------------------------ | ---------------------------------------- |
| 保存草稿      | `PUT /api/editor/draft`             | thread_id + content JSON | 200 + DraftLoad                          |
| 加载草稿      | `GET /api/editor/draft/{thread_id}` | thread_id                | 200 + DraftLoad（含之前保存的 content）  |
| 更新草稿      | `PUT /api/editor/draft`             | thread_id + 新 content   | 200 + 更新后的 DraftLoad                 |
| 不存在 thread | `GET /api/editor/draft/{thread_id}` | 随机 UUID                | 404                                      |
| 权限校验      | `PUT /api/editor/draft`             | 他人的 thread_id         | 404（thread not found or access denied） |

---

### 4.6 `test_cross_module_e2e.py` — 跨模块集成链路

#### 完整业务链路测试

```
创建 workspace
  → 获取上传 URL → 确认上传 → 查看文档状态
  → 创建 thread → 触发 run（Mock LLM）→ 获取 run 结果
  → 保存草稿 → 加载草稿 → 验证内容一致
  → 获取 workspace summary → 验证 document_count
```

#### 权限隔离测试

| 用例                           | 操作                                   | 预期    |
| ------------------------------ | -------------------------------------- | ------- |
| 用户 A 访问用户 B 的 workspace | GET /api/workspaces/{B's id}           | 404     |
| 用户 A 访问用户 B 的文档       | GET /api/documents/{B's doc id}        | 404     |
| 用户 A 访问用户 B 的 thread    | GET /api/agent/threads/{B's thread id} | 403/404 |

> **注**：权限隔离测试需要第二个测试用户。在 seed_data 中创建 user_b + 对应 token。

---

## 五、Mock 策略详解

### 5.1 dependency_overrides 注入点

```python
# conftest.py 中，创建 app 后立即注入
from backend.api.routers.agent import _get_lg_client

app.dependency_overrides[_get_lg_client] = lambda: mock_lg_client
```

### 5.2 MockLangGraphClient 行为规格

```python
class MockLangGraphClient:
    """返回确定性结果，用于断言。"""

    async def create_thread(self) -> dict:
        return {"thread_id": "mock-thread-001"}

    async def create_run(self, thread_id: str, input: dict) -> dict:
        return {"run_id": "mock-run-001", "status": "completed"}

    async def stream_events(self, thread_id: str, run_id: str) -> AsyncIterator[dict]:
        """生成 3 个固定 SSE 事件，便于断言数量和内容。"""
        events = [
            {"event": "on_chain_start", "data": {"name": "research_graph"}},
            {"event": "on_chat_model_stream", "data": {"chunk": "Hello"}},
            {"event": "on_chain_end", "data": {"output": "Done"}},
        ]
        for event in events:
            yield event

    # resume / cancel 等方法类似，记录调用参数供断言
    calls: list[tuple[str, dict]]  # (method_name, kwargs)
```

### 5.3 MockEmailService 行为规格

```python
class MockEmailService:
    """记录发送请求，不真实发邮件。测试可断言 sent_emails 列表。"""

    def __init__(self) -> None:
        self.sent_emails: list[dict] = []

    async def send_verification_email(self, to: str, token: str) -> None:
        self.sent_emails.append({"type": "verification", "to": to, "token": token})

    async def send_password_reset_email(self, to: str, token: str) -> None:
        self.sent_emails.append({"type": "password_reset", "to": to, "token": token})
```

### 5.4 MockOAuthProvider 行为规格

```python
class MockOAuthProvider:
    """固定返回预设用户信息，code 参数被忽略。"""
    provider_name: str = "github"

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        return f"https://github.com/login/oauth/authorize?state={state}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        return {
            "external_id": "github:12345",
            "email": "oauth-test@example.com",
            "display_name": "OAuth Test User",
        }
```

---

## 六、文件组织

### 6.1 新增文件

```
tests/e2e/
├── __init__.py             ← 已有
├── conftest.py             ← 重写：进程内 app + 种子数据 + Mock 注入
├── mocks/
│   ├── __init__.py
│   ├── mock_langgraph.py   ← MockLangGraphClient
│   ├── mock_oauth.py       ← MockOAuthProvider
│   └── mock_email.py       ← MockEmailService
├── seed.py                 ← SeedData dataclass + 种子数据创建函数
├── test_health.py          ← 已有，适配新 fixture
├── test_auth.py            ← 重写：扩充为完整认证测试
├── test_workspace.py       ← 新增
├── test_document.py        ← 新增
├── test_agent.py           ← 新增
├── test_editor.py          ← 新增
└── test_cross_module.py    ← 新增
```

### 6.2 修改文件

| 文件                       | 变更                                                 |
| -------------------------- | ---------------------------------------------------- |
| `tests/e2e/conftest.py`    | 重写：进程内 FastAPI app + ASGITransport + seed_data |
| `tests/e2e/test_health.py` | 适配新 fixture（`test_client` 替代 `e2e_client`）    |
| `tests/e2e/test_auth.py`   | 重写：从 2 个测试扩充到 20+ 个                       |
| `Makefile`                 | 新增 `test-e2e` target                               |
| `pyproject.toml`           | 确认 `e2e` marker 已存在（已有，无需修改）           |

---

## 七、运行方式与 CI 集成

### 7.1 本地运行

```bash
# 1. 启动基础设施
make infra

# 2. 运行数据库迁移
make db-upgrade

# 3. 仅运行 E2E 测试
make test-e2e
```

### 7.2 Makefile 新增 target

```makefile
test-e2e: ## 运行 E2E API 集成测试（需要 make infra）
	uv run pytest -m e2e -v --tb=short
```

### 7.3 CI 集成（GitHub Actions）

```yaml
# .github/workflows/ci.yml 中新增 job
e2e-tests:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: pgvector/pgvector:pg16
      env:
        POSTGRES_USER: postgres
        POSTGRES_PASSWORD: postgres
        POSTGRES_DB: research_copilot_test
      ports: ["5432:5432"]
      options: >-
        --health-cmd "pg_isready -U postgres"
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
    redis:
      image: redis:7-alpine
      ports: ["6379:6379"]
      options: >-
        --health-cmd "redis-cli ping"
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
    minio:
      image: minio/minio:latest
      ports: ["9000:9000"]
      env:
        MINIO_ROOT_USER: minioadmin
        MINIO_ROOT_PASSWORD: minioadmin
      # minio 需要 command，用 entrypoint override
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v3
    - run: uv sync --dev
    - run: uv run alembic upgrade head
      env:
        DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/research_copilot_test
    - run: uv run pytest -m e2e -v --tb=short
      env:
        DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/research_copilot_test
        REDIS_URL: redis://localhost:6379/0
        MINIO_ENDPOINT: localhost:9000
        JWT_SECRET: test-secret-for-ci
```

### 7.4 测试数据库隔离

- CI 中使用独立的 `research_copilot_test` 数据库
- 本地开发可复用 `research_copilot` 数据库（E2E 测试种子数据有唯一前缀，不会与开发数据冲突）
- 每次 E2E 测试 session 结束时，清理种子数据

---

## 八、影响范围与注意事项

### 8.1 不在范围内

- 浏览器级 E2E 测试（Playwright/Cypress）
- 前端组件测试（Jest/Vitest）
- Docker 部署拓扑验证（保留现有容器级冒烟测试）
- 性能/压力测试

### 8.2 前置条件

| 条件            | 说明                                                                  |
| --------------- | --------------------------------------------------------------------- |
| Auth 模块已实现 | `test_auth_e2e.py` 的注册/登录/OAuth 用例依赖 auth design spec 的实现 |
| Mock 接口对齐   | Mock 对象的方法签名需与真实实现保持一致                               |
| Docker 基础设施 | `make infra` 能正常启动 PG/Redis/MinIO                                |

### 8.3 实施建议

1. **先实现基础框架** — `conftest.py` + `seed.py` + `mocks/` + `test_health.py` 适配
2. **按模块逐步扩展** — workspace → document → editor → agent → auth → cross_module
3. **Auth 测试最后写** — 需等待 auth design spec 的实现完成
