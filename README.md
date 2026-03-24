# Research Copilot

> 意图驱动型自动案头研究工作站 —— 自然语言指令 → Agent 自主规划调度 → 高保真解析与安全沙盒验证 → 结构化成果一键交付。

面向高认知负荷深度脑力工作者，Research Copilot 将论文检索、精读摘要、Research Gap 识别、代码验证、模拟审稿、报告生成等科研全流程整合进一个交互式工作站。

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| **Supervisor + 6 Workflow** | LangGraph 驱动的多步 Agent，按需动态组合 Discovery → Extraction → Ideation → Execution → Critique → Publish |
| **Human-in-the-Loop** | 关键节点（论文选择、代码执行、报告定稿）自动挂起等待用户确认 |
| **RAG Pipeline** | MinerU GPU 版面解析 → 语义切块 → bge-m3 向量化 → pgvector 检索 |
| **安全沙盒** | Docker 隔离执行 Python 代码，无外网、超时自动销毁 |
| **Canvas 协同编辑** | TipTap v2 富文本编辑器，支持 Markdown + LaTeX 数学公式渲染 |
| **CoT 可视化** | 实时展示 Agent 思考链路，完整可观测 |
| **结构化交付** | Markdown 报告 + 学术 PDF (Typst/Beamer) + ZIP 归档包一键下载 |

---

## 🏗️ 系统架构

```
Web UI (React + TypeScript SPA)
   │  SSE / REST
   ▼
FastAPI BFF (鉴权 / 租户隔离 / Quota / 文件代理)
   │
   ├──► LangGraph Agent (Supervisor + 6 Workflow subgraphs)
   │       └──► Docker Sandbox (隔离执行)
   │
   ├──► RAG Pipeline (Celery Worker: MinerU → 切块 → Embed)
   │
   └──► PostgreSQL + pgvector (Checkpoint + 业务数据 + 向量索引)
```

详细架构文档见 [docs/ARCHITECT.md](docs/ARCHITECT.md)。

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 19 · TypeScript · Vite · TipTap v2 · shadcn/ui · TanStack Query · Zustand |
| **后端 BFF** | FastAPI · SQLAlchemy 2.0 (async) · Pydantic V2 · Alembic |
| **Agent** | LangGraph · LangChain (OpenAI / Anthropic / Google) |
| **RAG** | MinerU · bge-m3 · pgvector · Celery + Redis |
| **数据库** | PostgreSQL 16 + pgvector |
| **沙盒** | Docker SDK for Python |
| **部署** | Docker Compose · Nginx · Prometheus + Grafana + Loki |

---

## 🚀 快速开始

### 前置条件

- **Python** ≥ 3.11
- **Node.js** ≥ 18 + **pnpm**
- **Docker** + **Docker Compose**
- [**uv**](https://docs.astral.sh/uv/) — Python 包管理器

### 一键启动

```bash
# 1. 克隆仓库
git clone https://github.com/mengdehong/ResearchCopilot.git
cd ResearchCopilot

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 3. 安装全部依赖
make install

# 4. 启动基础设施 (PostgreSQL + Redis + MinIO)
make infra

# 5. 执行数据库迁移
make db-upgrade

# 6. 分别在三个终端启动服务
make dev-backend    # 后端 API (localhost:8000)
make dev-celery     # Celery Worker
make dev-frontend   # 前端 (localhost:5173)
```

本地开发详细说明见 [docs/development.md](docs/development.md)。

---

## 📁 目录结构

```
.
├── backend/                # Python 后端
│   ├── main.py             # FastAPI 入口
│   ├── api/                # 路由 + DTO
│   ├── agent/              # LangGraph Agent (Supervisor + 6 WF)
│   ├── services/           # 业务逻辑层
│   ├── repositories/       # 数据访问层 (Repository 模式)
│   ├── models/             # SQLAlchemy ORM
│   ├── clients/            # 外部系统连接器
│   ├── core/               # 配置 / DB / 日志 / 异常
│   └── workers/            # Celery 异步任务
├── frontend/               # React + TypeScript SPA
│   └── src/
│       ├── features/       # 按功能拆分 (chat / canvas / workspace ...)
│       ├── stores/         # Zustand 状态管理
│       └── components/     # 通用 UI 组件
├── deployment/             # Docker Compose + 监控
├── alembic/                # 数据库迁移
├── tests/                  # pytest 测试
├── docs/                   # 项目文档
├── pyproject.toml          # Python 依赖 (uv)
└── Makefile                # 开发命令集
```

---

## 🧪 测试

```bash
make test              # 全部测试
make test-unit         # 单元测试
make test-integration  # 集成测试 (需要基础设施)
make test-ui-mocked    # 前端 Playwright E2E
```

---

## 📝 代码质量

```bash
make lint       # Ruff 检查
make format     # Ruff 格式化
make typecheck  # MyPy 类型检查
make hooks      # 安装 Git pre-commit hooks
```

---

## 📄 License

Private — All rights reserved.
