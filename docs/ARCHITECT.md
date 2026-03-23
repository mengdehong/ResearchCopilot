# Research Copilot — 系统架构文档

> **产品定位**：面向高认知负荷深度脑力工作者的意图驱动型自动案头研究工作站。
> **核心价值**：自然语言指令 → Agent 自主规划调度 → 高保真解析与安全沙盒验证 → 结构化成果一键交付。

---

## 一、整体系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Web UI (React + TypeScript SPA / Vite)             │
│ ┌───────────────────────────┐ ┌───────────────────────────────────────────┐ │
│ │ 💬 左侧：Chat / 控制台    │ │ 📝 右侧：Canvas / 在线协同编辑器          │ │
│ │ - 发送指令 / 确认打断(HITL)││ - 富文本/Markdown 实时渲染与手动修改      │ │
│ │ - 接收 SSE Agent 思考状态 │ │ - PDF / 沙盒图表 / Research 结构化产物卡片  │ │
│ └──────────────┬────────────┘ └──────────────────────┬────────────────────┘ │
└────────────────┼─────────────────────────────────────┼──────────────────────┘
     WebSocket / │SSE (流式对话与状态推送) REST API 请求│ (防抖保存编辑器文档 /
                 │                                     │  上传文件附件)
┌────────────────▼─────────────────────────────────────▼──────────────────────┐
│                FastAPI Server (BFF / API Gateway 业务控制面)                │
│ - JWT 鉴权 | 租户 Workspace 隔离 | Quota 计费 | 文件上传代理(至 OSS/S3)     │
│ - Agent 状态同步桥接 (将用户在右侧手改的内容打包为 State 注入 Agent)        │
└────────────────┬─────────────────────────────────────┬──────────────────────┘
                 │ 转发 Agent 触发指令                 │ 投递文件解析异步任务
┌────────────────▼──────────────────┐   ┌──────────────▼──────────────────────┐
│ LangGraph Server (Agent 运行时)   │   │ RAG Ingestion Pipeline (后台离线管道)│
│                                   │   │ (由 Celery 或 MQ Worker 运行)       │
│ ┌───────────────────────────────┐ │   │ ┌──────────┐ ┌─────────┐ ┌────────┐ │
│ │ Supervisor Agent (主控大脑)   │ │   │ │ MinerU   │ │ Chunking│ │ Embed  │ │
│ │  ├─ 寻源初筛 WF (Discovery)   │ │   │ │ (GPU版面 │►│ 语义切块│►│ 向量化 │ │
│ │  ├─ 深度精读 WF (Extraction)  │ │   │ │ 解析引擎)│ └─────────┘ └────────┘ │
│ │  ├─ 实验推演 WF (Ideation)    │ │   │ └──────────┘                        │
│ │  ├─ 沙盒验证 WF (Execution)   │◄┼───┤                                     │
│ │  ├─ 模拟审稿 WF (Critique)    │ │   └─────────────────────────┬───────────┘
│ │  └─ 报告交付 WF (Publish)     │ │                             │ 异步写入
│ └──────────────┬────────────────┘ │   召回文献块                ▼
│   挂起/恢复    │ Thread 记忆读写  │  ────────────► ┌────────────────────────┐
│ (HITL 打断)    │ (Checkpointer)   │                │ PostgreSQL + pgvector  │
└────────────────┼──────────────────┘                │ (向量索引)             │
                 │                                   └────────────────────────┘
                 │ 请求 Docker Daemon
                 │ 动态启停执行 Python
                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🐳 Docker Sandbox (即用即毁隔离沙盒)                                        │
│ - 无外网权限 | 物理完全隔离 | 超时强制销毁                                  │
│ - 预装: Numpy, Pandas, PyTorch, Matplotlib, SciPy 等                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 🗄️ PostgreSQL (全局唯一真实数据源 Single Source of Truth)                   │
│ - LangGraph Checkpoints (Agent 多轮对话历史与图执行的断点状态)              │
│ - Users / Workspaces (SaaS 业务数据)                                        │
│ - Document State (生成的长文资产，含用户手动修改后的最终定稿版本)           │
│ - pgvector 扩展 (RAG 向量索引，与业务数据同库)                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 服务清单

| 服务                 | 职责                                               | 技术栈                                                                       |
| -------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Web UI**           | 双栏 SPA（Chat + Canvas 编辑器）                   | React + TypeScript + Vite + TipTap v2 + shadcn/ui + TanStack Query + Zustand |
| **FastAPI BFF**      | 鉴权 / 租户隔离 / 计费 / 文件代理 / Agent 状态桥接 | FastAPI + SQLAlchemy + Pydantic                                              |
| **LangGraph Server** | Agent 运行时（Supervisor + 6 子 Workflow）         | LangGraph Platform / langgraph-sdk                                           |
| **RAG Pipeline**     | 离线异步：PDF 解析 → 语义切块 → 向量化入库         | Celery Worker + MinerU + bge-m3 / bge-reranker-v2                            |
| **Docker Sandbox**   | 即用即毁的隔离 Python 执行环境                     | Docker SDK for Python                                                        |
| **PostgreSQL**       | SSOT：Checkpoint + 业务数据 + 文档状态 + pgvector  | PostgreSQL 16 + pgvector 扩展                                                |

### 技术选型决策

| 决策项     | 选择                             | 理由                                                                 |
| ---------- | -------------------------------- | -------------------------------------------------------------------- |
| Agent 框架 | LangGraph                        | 原生 subgraph 嵌套、Checkpoint 持久化、interrupt() HITL              |
| LLM 模型层 | Provider-agnostic（商业 + 本地） | LangChain ChatModel 抽象，支持 OpenAI/Anthropic/Google + Ollama/vLLM |
| 前端框架   | React + TypeScript + Vite        | 生态最大，`@langchain/langgraph-sdk` 官方 TS 客户端                  |
| 后端 BFF   | FastAPI                          | 异步原生，Pydantic 类型安全，团队经验                                |
| 向量数据库 | pgvector                         | 与 PostgreSQL 同库，部署简单，MVP 阶段够用                           |
| PDF 解析   | MinerU                           | GPU 加速版面分析，双栏/公式/表格精准还原                             |
| 编辑器     | TipTap v2                        | 扩展性最强，学术 Markdown + 公式支持好，不自研重度编辑器             |


### 文件组织
```
.
├── deployment/                     # 部署与环境编排
│   ├── sandbox_image/              # 核心：科研 Python 沙盒专属 Dockerfile（无外网，预装科学库）
│   └── docker-compose.yml          # PG、Redis、后端、Worker 一键编排
│
├── pyproject.toml                  # 依赖管理 uv
│
├── backend/                        # 核心源代码目录
│   ├── main.py                     # FastAPI 启动入口
│   │
│   ├── api/                        # 控制面：API 网关层（懂 HTTP，不处理 AI 逻辑）
│   │   ├── dependencies.py         # 依赖注入（JWT 鉴权、Workspace、DB Session）
│   │   ├── schemas/                # Pydantic 模型（请求/响应 DTO）
│   │   │   ├── auth.py             # TokenPayload, UserInfo
│   │   │   ├── agent.py            # RunRequest, RunEvent, InterruptResponse
│   │   │   ├── document.py         # UploadInit, UploadConfirm, DocumentMeta
│   │   │   ├── workspace.py        # WorkspaceCreate, WorkspaceDetail
│   │   │   └── editor.py           # DraftSave, DraftLoad
│   │   └── routers/                # 路由分组
│   │       ├── auth.py             # 租户与账号隔离
│   │       ├── agent.py            # Agent 触发、SSE 流、HITL 交互
│   │       ├── document.py         # 文献上传与解析任务分发
│   │       ├── workspace.py        # Workspace CRUD
│   │       └── editor.py           # 草稿保存/加载
│   │
│   ├── agent/                      # 智能面：Agent 运行时（由 LangGraph Server 加载，不在 BFF 内）
│   │   ├── state.py                # SharedState + SupervisorState + 各 WF State
│   │   ├── graph.py                # 主图（Supervisor + 检查点回评 + 条件路由）
│   │   ├── workflows/              # 子图（各专家流程，物理隔离）
│   │   │   ├── 1_discovery/        # 寻源初筛：Arxiv/PubMed 检索、Meta 提取、触发异步解析
│   │   │   │   ├── state.py        # DiscoveryState 定义（查询参数、候选列表、评分）
│   │   │   │   ├── nodes.py        # 检索节点、排序过滤节点、Meta 提取节点
│   │   │   │   └── graph.py        # Discovery subgraph 编排
│   │   │   ├── 2_extraction/       # 深度精读：定向 RAG 召回、跨文档对比、术语表构建
│   │   │   │   ├── state.py        # ExtractionState 定义（论文集、精读笔记、对比矩阵）
│   │   │   │   ├── nodes.py        # RAG 召回节点、跨文档对比节点、术语提取节点
│   │   │   │   └── graph.py        # Extraction subgraph 编排
│   │   │   ├── 3_ideation/         # 实验推演：Research Gap 识别、Baseline 设计、评估指标
│   │   │   │   ├── state.py        # IdeationState 定义（Gap 分析、实验方案、评估体系）
│   │   │   │   ├── nodes.py        # Gap 分析节点（含 3 步 CoT）、方案生成节点、指标设计节点
│   │   │   │   └── graph.py        # Ideation subgraph 编排
│   │   │   ├── 4_execution/        # 沙盒验证：代码生成、HITL 确认、Docker 隔离执行、Debug 重试
│   │   │   │   ├── state.py        # ExecutionState 定义（代码、执行结果、重试计数）
│   │   │   │   ├── nodes.py        # 代码生成节点、沙盒执行节点、反思重试节点
│   │   │   │   └── graph.py        # Execution subgraph 编排（含 interrupt + max_retries 循环）
│   │   │   ├── 5_critique/         # 模拟审稿：红蓝对抗、逻辑检测、structured feedback
│   │   │   │   ├── state.py        # CritiqueState 定义（审查输入、feedback、通过/打回判定）
│   │   │   │   ├── nodes.py        # 支持者节点、批评者节点、裁决节点（三方独立 LLM 调用）
│   │   │   │   └── graph.py        # Critique subgraph 编排（线性流程，打回由 Supervisor 处理）
│   │   │   └── 6_publish/          # 报告交付：大纲组装、Markdown 生成、PPTX 渲染、ZIP 打包
│   │   │       ├── state.py        # PublishState 定义（大纲、报告内容、输出文件路径）
│   │   │       ├── nodes.py        # 大纲组装节点、报告生成节点、PPTX 渲染节点、打包节点
│   │   │       └── graph.py        # Publish subgraph 编排（含 interrupt 定稿确认）
│   │   ├── tools/                  # 工具层（供 LLM 调用）
│   │   │   ├── arxiv_tool.py
│   │   │   └── sandbox_tool.py     # 调用 services 层逻辑
│   │   ├── prompts/                # 提示词管理（YAML baseline + DB 覆盖层）
│   │   │   ├── _loader.py          # PromptLoader：YAML → DB override → 最终 prompt
│   │   │   ├── supervisor/         # Supervisor 骨架 + 学科 snippet
│   │   │   ├── discovery/          # Discovery WF 节点 prompt
│   │   │   ├── extraction/         # Extraction WF 节点 prompt
│   │   │   ├── ideation/           # Ideation WF 节点 prompt（含 3 步 CoT）
│   │   │   ├── execution/          # Execution WF 节点 prompt
│   │   │   ├── critique/           # Critique WF 三方独立 prompt
│   │   │   └── publish/            # Publish WF 节点 prompt
│   │   └── skills/                 # Skill 能力单元（SkillRegistry 启动时扫描注册）
│   │       ├── registry.py         # SkillRegistry 实现
│   │       ├── base.py             # SkillDefinition 数据结构
│   │       ├── arxiv_search/       # mode=tool: 论文检索 Skill
│   │       ├── pdf_to_markdown/    # mode=tool: PDF 转 Markdown Skill
│   │       └── ppt_generation/     # mode=subgraph: PPT 生成 Skill
│   │
│   ├── services/                   # 业务逻辑层（BFF 侧 + Agent 侧共用）
│   │   ├── agent_service.py        # BFF: Agent 触发、Thread 管理、SSE 事件翻译、HITL
│   │   ├── document_service.py     # BFF: 预签名 URL、上传确认、解析重试
│   │   ├── workspace_service.py    # BFF: Workspace CRUD + 聚合摘要
│   │   ├── editor_service.py       # BFF: 草稿自动保存 + 提交版查询
│   │   ├── quota_service.py        # BFF: 配额检查、消耗记录、业务限流
│   │   ├── sandbox_manager.py      # Agent: Docker 控制（容器启动、代码注入、结果提取）
│   │   ├── parser_engine.py        # Worker: MinerU 解析封装
│   │   ├── rag_engine.py           # Agent: 切块、Embedding、向量数据库交互
│   │   └── llm_gateway.py          # 共用: LLM 统一封装（多模型适配、限流降级）
│   │
│   ├── repositories/               # 数据访问层（Repository 模式，接收 AsyncSession）
│   │   ├── base.py                 # BaseRepository[T] — 通用 CRUD 泛型基类
│   │   ├── user_repo.py            # 用户数据访问
│   │   ├── workspace_repo.py       # Workspace + 成员关系查询
│   │   ├── document_repo.py        # 文档元数据 CRUD + 状态流转
│   │   ├── editor_repo.py          # 草稿读写
│   │   ├── run_snapshot_repo.py    # Run 输入快照 + 状态查询
│   │   └── quota_repo.py           # Token 消耗记录 + 统计查询
│   │
│   ├── clients/                    # 外部系统连接器层
│   │   ├── langgraph_client.py     # langgraph-sdk HTTP Client 封装
│   │   ├── storage_client.py       # S3/MinIO（预签名 URL、head_object、删除）
│   │   └── auth_client.py          # 第三方 Auth JWT 验证 + 用户信息获取
│   │
│   ├── models/                     # SQLAlchemy ORM 模型
│   │   ├── user.py                 # 用户（同步自第三方 Auth）
│   │   ├── workspace.py            # Workspace + 成员关系
│   │   ├── document.py             # 文档元数据
│   │   ├── editor_draft.py         # 编辑器草稿
│   │   ├── run_snapshot.py         # Run 输入快照
│   │   └── quota_record.py         # Token 消耗记录
│   │
│   ├── core/                       # 全局核心组件
│   │   ├── config.py               # 配置加载（BaseSettings）
│   │   ├── database.py             # PostgreSQL + LangGraph Checkpointer
│   │   ├── exceptions.py           # 自定义异常类型 + 全局异常处理器
│   │   └── logger.py               # 结构化日志（structlog, 支持 Trace ID）
│   │
│   └── workers/                    # 异步任务（CPU/GPU 密集型）
│       ├── celery_app.py           # 队列配置（Redis / RabbitMQ）
│       └── tasks/
│           └── ingestion.py        # PDF 解析与向量化任务
│
└── frontend/src/
    ├── app/                        # 应用入口 + 路由 + Provider + Layout
    │   ├── App.tsx                  # 根组件
    │   ├── router.tsx               # React Router 路由配置
    │   ├── RootLayout.tsx           # 全局 Provider 注入层
    │   └── AppLayout.tsx            # 认证守卫 + GlobalNav
    │
    ├── components/                  # 通用 UI 组件
    │   ├── ui/                      # shadcn/ui 基础组件（Button、Dialog、Tabs 等）
    │   └── shared/                  # 跨 feature 复用组件
    │       ├── AcademicMarkdown.tsx  # Markdown + KaTeX 数学公式渲染
    │       ├── StatusBar.tsx         # 底部 Agent 状态栏
    │       └── FileDropzone.tsx      # 文件拖拽上传区
    │
    ├── features/                    # 核心业务模块（Feature-Sliced，按功能拆分）
    │   ├── auth/                    # 认证流程
    │   ├── workspace/               # 课题空间管理（Sidebar + Dashboard）
    │   ├── chat/                    # 左栏：对话控制区（ChatPanel、CoTTree、HITLCard）
    │   ├── canvas/                  # 右栏：多 Tab 工作区（editor/pdf/sandbox/research）
    │   ├── documents/               # 文献管理（上传、状态、解析产物）
    │   ├── settings/                # 设置（学科偏好、BYOK、用量统计）
    │   └── workbench/               # WorkbenchPage 组装层（组合 Chat + Canvas）
    │
    ├── stores/                      # Zustand 状态管理
    │   ├── useAgentStore.ts         # SSE 实时状态（messages、cotTree、interrupt、generatedContent）
    │   └── useLayoutStore.ts        # UI 瞬态（sidebarCollapsed、splitRatio）
    │
    ├── lib/                         # 工具函数（Axios、cn、polling）
    └── types/                       # 全局 TS 类型定义（对齐后端 schemas）

```


---

## 二、Agent 设计架构

### 总览

采用 **Supervisor + 专家子 Workflow** 模式。Supervisor 负责意图识别与动态任务编排，6 个专家 Workflow 作为 LangGraph subgraph 各自专注单一职责。路由策略采用 **硬规则门禁 + LLM 结构化输出 + Pre-plan 检查点回评** 混合模式。

```
                               ┌───────────────────────────────────┐
                               │   Supervisor Agent (主控大脑)      │
                               │ - 硬规则门禁 + LLM 结构化输出路由  │
                               │ - Pre-plan + 检查点回评            │
                               │ - Thread 全局上下文记忆管理        │
                               └──────────────┬────────────────────┘
                                              │ 按需动态调度
       ┌──────────────┬───────────────┬───────┼───────┬───────────────┬──────────────┐
       ▼              ▼               ▼       │       ▼               ▼              ▼
┌─────────────┐┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐┌─────────────┐
│1. 寻源初筛WF││2. 深度精读WF ││3. 实验推演WF ││4. 沙盒验证WF ││5. 模拟审稿WF ││6. 报告交付WF│
│ (Discovery) ││ (Extraction) ││ (Ideation)   ││ (Execution)  ││ (Critique)   ││ (Publish)   │
└──────┬──────┘└──────┬───────┘└──────┬───────┘└──────┬───────┘└──────┬───────┘└──────┬──────┘
       │              │               │               │               │               │
  调用外部 API   跨文档拉表对比  寻找 Research Gap  动态拉起容器    红蓝对抗挑刺    Marp/LaTeX排版
  提取 Meta 信息 定向 RAG 召回   制定 Baseline     执行 Python 代码 逻辑漏洞检测   Markdown 生成
 【轻量级动作】 【强依赖视觉模型】生成评估指标体系  自动 Debug 重试  拒绝并打回重做  插入文献角标
```

### 科研 Pipeline 流程

6 个 Workflow 对齐真实科研工作流，Supervisor 按需动态组合：

```
Discovery → Extraction → Ideation → Execution → Critique → Publish
  找论文  →  读透内容  → 找Gap设计方案 → 跑代码验证 → 自我审稿 → 输出成果
```

### 各 Workflow 详细设计

#### 1. 寻源初筛 WF (Discovery)

| 项           | 描述                                                                                                                                                                       |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **输入**     | 用户查询关键词 / 论文标题 / DOI / Arxiv ID                                                                                                                                 |
| **内部流程** | Arxiv/PubMed API 语义检索 → 结果排序过滤 → LLM 生成相关性评语 → `interrupt()` 展示候选列表供用户勾选 → 对选中论文通过 BFF document service 触发 RAG Ingestion 异步解析入库 |
| **输出**     | 候选文献列表 + 用户选中的论文 ID + ingestion 任务 ID                                                                                                                       |
| **特点**     | 轻量级，不做深度阅读；用户通过 abstract + 相关性评语做选择，无需 RAG；ingestion 仅对选中论文触发                                                                           |

#### 2. 深度精读 WF (Extraction)

| 项           | 描述                                                                                                                                                        |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **输入**     | 指定的论文集（来自 Discovery 选中或用户上传，两种来源统一通过 BFF document service 触发 ingestion）                                                         |
| **内部流程** | 等待 RAG Pipeline 解析完成 → 增量检查（跳过已有笔记的论文）→ 定向 RAG 召回关键段落 → 跨文档拉表对比方法论 → 提取创新点/实验设置/结论 → 构建术语表(Glossary) |
| **输出**     | 结构化精读笔记 + 跨文献对比矩阵 + 术语表 + 引用溯源映射                                                                                                     |
| **特点**     | 强依赖视觉模型解析质量（MinerU），是内容准确性的基石；支持增量分析（追加论文时不重做已有笔记）                                                              |

#### 3. 实验推演 WF (Ideation)

| 项           | 描述                                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------------------- |
| **输入**     | 精读笔记 + 用户研究方向（从 `artifacts["supervisor"]["research_direction"]` 获取，Supervisor 规划时自动提取） |
| **内部流程** | 分析现有工作局限 → 识别 Research Gap → 提出假设和实验方案 → 制定 Baseline 和对比方法 → 生成评估指标体系       |
| **输出**     | Research Gap 分析 + 实验方案草案 + Baseline 列表 + 评估指标                                                   |
| **特点**     | 最具创造性的环节，核心依赖 LLM 推理能力和学科专家 Prompt                                                      |

#### 4. 沙盒验证 WF (Execution)

| 项           | 描述                                                                                                                                                           |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **输入**     | 实验方案 / 算法描述 / 用户直接下达的代码任务                                                                                                                   |
| **内部流程** | LLM 生成 Python 代码 → `interrupt()` 请求用户确认 → Docker Sandbox 隔离执行 → 捕获 stdout/stderr/图表 → 失败则 LLM 自我反思重写（max 3 轮） → 超时强制销毁容器 |
| **输出**     | 执行结果 + 可视化图表文件 + 调试通过的 .py 脚本                                                                                                                |
| **特点**     | 核心护城河，HITL 必须经过用户确认才执行代码                                                                                                                    |

#### 5. 模拟审稿 WF (Critique)

| 项           | 描述                                                                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **输入**     | 上游任意 Workflow 的产出物                                                                                                                 |
| **内部流程** | 红蓝**并行**对抗审查（支持者和批评者独立调用 LLM，互不可见）→ 裁决节点合并两方意见 → 生成 structured feedback → 若不通过则打回上游 WF 重做 |
| **输出**     | 审稿意见（通过/打回 + 具体修改建议），按审查目标分命名空间存储（`artifacts["critique"][target_wf]`）                                       |
| **特点**     | 质量门禁，Supervisor 根据 feedback 自动将任务重新注入上游 WF，形成 Plan→Execute→Critique→Re-plan 自主迭代循环                              |

#### 6. 报告交付 WF (Publish)

| 项           | 描述                                                                                                                                                                                                                                            |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **输入**     | 经 Critique 审查通过的全部中间产物                                                                                                                                                                                                              |
| **内部流程** | 组装汇报大纲 → LLM 生成结构化 Markdown → `interrupt()` 请求用户确认定稿（approve→继续 / reject→推送至 Canvas 编辑器由用户手改，改完确认后回流）→ ppt_generation Skill 渲染学术 PDF → 插入文献引用角标 → 打包 ZIP（原始文献+报告+代码+图表+PDF） |
| **输出**     | Markdown 报告 + 学术 PDF（Typst/Beamer 编译） + 可下载 ZIP 归档包                                                                                                                                                                               |
| **特点**     | 只交付生产力资产；用户可在 Canvas 编辑器中精修 Markdown 后再触发渲染；PPT 输出为 PDF 格式（Typst 主推，Beamer 预留）                                                                                                                            |

### 关键机制

| 机制                  | 实现方式                                                                                                                                                                                                                                       |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Human-in-the-loop** | LangGraph `interrupt()` 挂起 → 前端弹出确认卡片 → `Command(resume=...)` 恢复。触发点：Discovery 论文勾选、沙盒执行前（MVP:approve/reject）、报告定稿前（reject→Canvas 手改）                                                                   |
| **流式状态推送**      | SSE 推送 Agent 当前执行节点 + CoT 日志至前端 Chat 区                                                                                                                                                                                           |
| **Critique 打回循环** | Critique WF 输出 structured feedback → 检查点回评节点将 feedback 以 messages 注入上游 WF → 重新执行 → 再送回 Critique（max 2 轮迭代）                                                                                                          |
| **错误重试**          | 沙盒 WF 内置 max_retries=3 循环；文献检索失败走降级提示                                                                                                                                                                                        |
| **学科切换**          | Supervisor 骨架 prompt + 学科 snippet YAML 文件注入（YAML baseline，DB 可覆盖），用户在设置中配置                                                                                                                                              |
| **Skill 系统**        | 四层体系（Tool→Skill→Workflow→Supervisor）。SkillRegistry 启动时扫描注册，mode=tool 绑定 Supervisor，mode=subgraph 嵌入 Workflow                                                                                                               |
| **任务控制**          | 用户可随时暂停/恢复/终止(Kill)后台异步任务，通过 Thread 状态管理                                                                                                                                                                               |
| **状态通知**          | 长耗时任务完成/异常时，通过站内 UI 通知（后续支持邮件）                                                                                                                                                                                        |
| **可观测性**          | 渐进式方案：MVP 阶段 structlog 结构化日志 + trace_id 跨服务传播 + LangSmith LLM 追踪 + FastAPI Metrics 端点；生产阶段升级 Grafana + Prometheus + Loki 全栈监控。详见 [可观测性设计](docs/superpowers/specs/2026-03-19-observability-design.md) |

### 动态组合示例

Supervisor 根据用户意图**动态选择 Workflow 组合**，不一定每次走完全链路：

| 用户指令示例                     | 触发的 Workflow                                                    |
| -------------------------------- | ------------------------------------------------------------------ |
| "帮我检索 Transformer 最新进展"  | Discovery                                                          |
| "把这 5 篇论文做个对比分析"      | Extraction                                                         |
| "这个领域还有什么可以做的方向？" | Discovery → Extraction → Ideation                                  |
| "验证一下这个公式"               | Execution                                                          |
| "检查一下这篇综述有没有逻辑问题" | Critique                                                           |
| "把分析结果做成 PPT"             | Publish                                                            |
| "从调研到出报告，全自动来一套"   | Discovery → Extraction → Ideation → Execution → Critique → Publish |
