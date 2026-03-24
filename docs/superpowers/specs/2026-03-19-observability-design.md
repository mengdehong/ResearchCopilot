# Research Copilot — 可观测性设计文档

> **定位**：日志、指标、追踪三大可观测性支柱的统一规划，覆盖 MVP 与生产两个阶段。
> **策略**：渐进式——Phase 2-5 零额外组件（代码层埋点 + LangSmith），Phase 8 升级为 Grafana + Prometheus + Loki 全栈监控。

---

## 一、设计原则

1. **结构化优先** — 所有日志为 JSON（生产）或结构化终端（开发），禁止裸字符串拼接
2. **trace_id 贯穿** — 每条请求链路从 BFF 到 Agent 到 Worker 共享同一 trace_id
3. **凭证脱敏** — API Key / JWT / Password 等安全敏感字段自动 `***` 脱敏；对话内容和论文片段保留（调试需要）
4. **渐进增强** — MVP 阶段不引入额外基础设施，所有可观测能力通过代码内埋点 + SaaS 服务实现

---

## 二、日志规范（全局，跨所有 Phase）

### 2.1 日志分级规则

| 级别       | 使用场景               | 示例                                                        |
| ---------- | ---------------------- | ----------------------------------------------------------- |
| `DEBUG`    | 开发调试细节，生产不开 | SQL 查询参数、LLM prompt 全文                               |
| `INFO`     | 正常业务事件           | 用户创建 Workspace、Agent 开始执行 WF、PDF 解析完成         |
| `WARNING`  | 异常但可自愈           | LLM 降级切换模型、Celery 任务重试、容器销毁失败（后台清理） |
| `ERROR`    | 需要人工关注           | DB 连接失败、LLM 全部 provider 不可用、S3 上传失败          |
| `CRITICAL` | 系统不可用             | 数据库迁移失败、核心服务启动失败                            |

### 2.2 结构化字段规范

每条日志通过 structlog contextvars 自动注入以下上下文字段：

**全局字段（所有服务）：**

| 字段           | 来源                       | 说明                              |
| -------------- | -------------------------- | --------------------------------- |
| `trace_id`     | BFF 中间件生成，跨服务传播 | 请求级唯一 ID                     |
| `service`      | 进程启动时静态绑定         | `bff` / `agent` / `celery-worker` |
| `user_id`      | JWT 鉴权后注入             | 当前用户                          |
| `workspace_id` | 路由参数/任务参数          | 当前工作空间                      |

**服务层专属字段：**

| 服务          | 追加字段                              |
| ------------- | ------------------------------------- |
| Agent         | `workflow`, `node`, `run_id`          |
| Celery Worker | `task_name`, `task_id`, `document_id` |
| Sandbox       | `container_id`, `execution_time_ms`   |

### 2.3 敏感字段脱敏

在 structlog processor 链中添加 `sanitize_sensitive_fields` processor，对以下 key 的 value 做 `***` 替换：

```
脱敏字段名单：api_key, secret, token, password, jwt, authorization
```

匹配方式：字段名包含上述子串（不区分大小写）即脱敏。

> 该 processor 应在 Phase 2 开始时追加到已有的 `logger.py` 中。

### 2.4 业务关键日志点

以下事件必须在 **INFO 级别** 输出结构化日志：

| 事件               | 日志字段                                               | 所属服务         |
| ------------------ | ------------------------------------------------------ | ---------------- |
| Agent run 开始     | `run_id`, `thread_id`, `user_message_preview`          | Agent            |
| Workflow 进入/退出 | `workflow`, `duration_ms`                              | Agent            |
| LLM 调用完成       | `model`, `input_tokens`, `output_tokens`, `latency_ms` | LLM Gateway      |
| Sandbox 执行       | `container_id`, `exit_code`, `duration_ms`, `timeout`  | Sandbox Manager  |
| Celery 任务完成    | `task_name`, `document_id`, `duration_ms`, `status`    | Celery Worker    |
| 文件状态变更       | `document_id`, `old_status`, `new_status`              | Document Service |

---

## 三、MVP 阶段实现（Phase 2-5）

MVP 目标：**零额外组件部署**，出问题时能通过终端日志 + LangSmith 定位根因。

### 3.1 trace_id 跨服务传播

```
用户请求 → BFF RequestIDMiddleware 生成 UUID trace_id
         → structlog contextvars 绑定（本进程所有日志自动携带）
         → 传给 LangGraph Server（HTTP Header: X-Trace-ID）
         → 传给 Celery Worker（task kwargs: trace_id）
```

**实现分布：**

| 组件             | 实现位置                                                                       | Phase   |
| ---------------- | ------------------------------------------------------------------------------ | ------- |
| BFF 中间件       | `backend/api/middleware.py` — `RequestIDMiddleware`                            | Phase 5 |
| LangGraph Client | `backend/clients/langgraph_client.py` — 每次请求带 `X-Trace-ID` header         | Phase 5 |
| Celery Worker    | `backend/workers/celery_app.py` — `task_prerun` signal 从 kwargs 恢复 trace_id | Phase 6 |

### 3.2 LangSmith 集成（LLM 可观测）

纯配置接入，零代码改动：

- **配置**：`config.py` 追加 `langsmith_api_key: str | None = None`
- **环境变量**：`.env` 中设置 `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY=xxx`
- **原理**：LangChain 框架检测到环境变量后自动上报所有 LLM 调用的 prompt / response / latency / token
- **覆盖**：Supervisor 路由、Workflow 节点内所有 `ChatModel.invoke()` 调用

> Phase 2 实现 `llm_gateway.py` 时同步配置。

### 3.3 FastAPI 基础 Metrics

使用 `prometheus-fastapi-instrumentator` 自动暴露 `/metrics` 端点：

```python
# backend/main.py
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

自动采集指标：
- 请求延迟直方图（`http_request_duration_seconds`）
- QPS（`http_requests_total`）
- 状态码分布
- 活跃请求数

> MVP 阶段只暴露端点不部署 Prometheus，为 Phase 8 预备。Phase 5 实现 BFF 时接入。

---

## 四、生产阶段实现（Phase 8 升级）

### 4.1 监控栈架构

```
┌──────────────────────────────────────────────────────────────┐
│                        Grafana                               │
│   Dashboard 1: 系统总览    Dashboard 2: Agent    Dashboard 3: RAG │
│   告警规则 → Grafana UI（后续可加 Webhook）                  │
└──────────┬───────────────────┬───────────────────────────────┘
           │                   │
    ┌──────▼──────┐    ┌───────▼───────┐
    │ Prometheus   │    │    Loki       │
    │ 抓 /metrics  │    │ Docker 日志   │
    └──────┬──────┘    └───────┬───────┘
           │                   │
    /metrics 端点         Docker log driver
           │                   │
    ┌──────┴───────────────────┴──────┐
    │         应用服务层               │
    │  FastAPI / LangGraph / Celery   │
    └──────────────────────────────────┘
```

### 4.2 docker-compose 新增服务

```yaml
# deployment/docker-compose.yml 新增
services:
  prometheus:
    image: prom/prometheus:v2.51.0
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"

  grafana:
    image: grafana/grafana:10.4.0
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

配套文件：
- `deployment/prometheus/prometheus.yml` — scrape 配置
- `deployment/grafana/provisioning/datasources/` — 自动注册 Prometheus + Loki 数据源
- `deployment/grafana/provisioning/dashboards/` — 预置 Dashboard JSON

### 4.3 自定义 Metrics

在 services 层手动注册 Prometheus 指标：

| Metric 名称                          | 类型      | 标签                 | 来源文件             |
| ------------------------------------ | --------- | -------------------- | -------------------- |
| `llm_request_duration_seconds`       | Histogram | `model`, `provider`  | `llm_gateway.py`     |
| `llm_tokens_total`                   | Counter   | `model`, `direction` | `llm_gateway.py`     |
| `sandbox_execution_duration_seconds` | Histogram | `exit_code`          | `sandbox_manager.py` |
| `sandbox_executions_total`           | Counter   | `status`             | `sandbox_manager.py` |
| `celery_task_duration_seconds`       | Histogram | `task_name`          | `celery_app.py`      |
| `agent_workflow_duration_seconds`    | Histogram | `workflow`           | Agent `graph.py`     |
| `agent_critique_rejections_total`    | Counter   | `target_workflow`    | Critique `nodes.py`  |

### 4.4 预置 Dashboard

**Dashboard 1 — 系统总览：**
- 各服务健康状态（UP/DOWN）
- HTTP 请求 QPS + 错误率 + P95 延迟
- DB 连接池使用率
- Celery 队列深度 + 活跃 Worker 数

**Dashboard 2 — Agent 运行：**
- 各 Workflow 执行次数 + 平均耗时
- Critique 打回率
- Sandbox 成功/失败/超时比例
- LLM token 消耗趋势（从 `quota_records` 表统计）

**Dashboard 3 — RAG Pipeline：**
- PDF 解析队列积压
- 解析耗时分布
- 向量化吞吐量

### 4.5 告警规则

初始告警仅在 Grafana UI 显示，后续按需加 Webhook（飞书/钉钉/Slack）：

| 告警            | 条件                                           | 严重级别 |
| --------------- | ---------------------------------------------- | -------- |
| 服务不可达      | `/health` 连续 3 次失败                        | Critical |
| API 错误率飙升  | 5xx > 5%（5 分钟窗口）                         | Warning  |
| LLM 全部不可用  | `llm_request_duration_seconds` 无数据 > 2 分钟 | Critical |
| Celery 队列积压 | 待处理任务 > 50（持续 10 分钟）                | Warning  |
| DB 连接池耗尽   | 使用率 > 90%                                   | Warning  |
| Sandbox 超时率  | timeout 占比 > 30%（15 分钟窗口）              | Warning  |

---

## 五、与现有 Phase 的集成

> Phase 1 已完成。可观测性增强从 Phase 2 开始渗透。

| Phase       | 追加内容                                                                                                                         | 改动量 |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------- | ------ |
| **Phase 2** | `logger.py` 追加 `sanitize_sensitive_fields` processor。`config.py` 追加 LangSmith 配置字段。各 Service 实现时遵循 §2.4 日志规范 | 小     |
| **Phase 3** | Agent `graph.py` / 各 WF `nodes.py` 按 §2.4 添加 workflow/node 级日志。Supervisor 路由决策带 `reasoning` 字段                    | 小     |
| **Phase 5** | BFF `RequestIDMiddleware`（trace_id 生成+传播）。`prometheus-fastapi-instrumentator` 接入。AccessLog 中间件                      | 中     |
| **Phase 6** | Celery `task_prerun` signal 恢复 trace_id。任务完成日志                                                                          | 小     |
| **Phase 8** | docker-compose 加 Prometheus + Loki + Grafana。预置 Dashboard + 告警规则。自定义 Metrics 埋点                                    | 大     |

### 新增依赖

| 依赖                                | 引入时机                  |
| ----------------------------------- | ------------------------- |
| `prometheus-fastapi-instrumentator` | Phase 5                   |
| `prometheus-client`                 | Phase 8（自定义 Metrics） |

---

## 六、未来扩展（当前不实现）

| 方向              | 说明                                                                |
| ----------------- | ------------------------------------------------------------------- |
| **前端监控**      | React SPA 可接入 Sentry（`@sentry/react`），捕获 JS 异常 + 性能指标 |
| **分布式追踪**    | Grafana Tempo 或 Jaeger，替代 LangSmith 覆盖非 LLM 链路             |
| **告警通知**      | Grafana Webhook → 飞书/钉钉/Slack Bot                               |
| **日志审计**      | 用户操作审计日志（独立表，不混入运行日志）                          |
| **自建 LLM 追踪** | Langfuse 自部署替换 LangSmith，实现数据主权                         |
