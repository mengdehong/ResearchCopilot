# Research Copilot

科研工作站 —— 论文检索、精读摘要、实验推演、代码验证、审稿反馈、报告生成，一站式完成。

---

## 功能概览

- **论文检索与筛选** — 对接 Arxiv / PubMed，批量检索、相关性评分、用户勾选确认
- **文献精读** — PDF 版面解析 → 语义切块 → 向量检索，跨文档对比与术语提取
- **实验推演** — Research Gap 识别、Baseline 设计、评估指标生成
- **代码验证** — Docker 沙盒隔离执行，自动 Debug 重试（最多 3 轮）
- **模拟审稿** — 红蓝对抗审查，结构化意见反馈，不通过自动打回重做
- **报告交付** — Markdown + 学术 PDF (Typst/Beamer) + ZIP 归档包下载
- **在线编辑器** — TipTap 富文本编辑，支持 Markdown 与 LaTeX 公式

---

## 架构

```
Web UI (React + TypeScript)
   │  SSE / REST
   ▼
FastAPI 后端 (鉴权 · 租户隔离 · 配额 · 文件代理)
   │
   ├──► LangGraph 任务调度 (6 个子工作流)
   │       └──► Docker 沙盒
   │
   ├──► 文献处理管线 (Celery: MinerU 解析 → 切块 → 向量化)
   │
   └──► PostgreSQL + pgvector
```

详细架构文档见 [docs/ARCHITECT.md](docs/ARCHITECT.md)。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 19 · TypeScript · Vite · TipTap v2 · shadcn/ui · TanStack Query · Zustand |
| **后端** | FastAPI · SQLAlchemy 2.0 (async) · Pydantic V2 · Alembic |
| **任务调度** | LangGraph · LangChain (OpenAI / Anthropic / Google) |
| **文献处理** | MinerU · bge-m3 · pgvector · Celery + Redis |
| **数据库** | PostgreSQL 16 + pgvector |
| **沙盒** | Docker SDK for Python |
| **部署** | Docker Compose · Nginx · Prometheus + Grafana + Loki |

---

## 快速开始

### 前置条件

- Python ≥ 3.11
- Node.js ≥ 18 + pnpm
- Docker + Docker Compose
- [uv](https://docs.astral.sh/uv/)

### 启动

```bash
# 1. 克隆 & 配置
git clone https://github.com/mengdehong/ResearchCopilot.git
cd ResearchCopilot
cp .env.example .env   # 编辑填入 API Key

# 2. 安装依赖
make install

# 3. 启动基础设施 + 数据库迁移
make infra
make db-upgrade

# 4. 启动服务（三个终端）
make dev-backend    # localhost:8000
make dev-celery
make dev-frontend   # localhost:5173
```

本地开发详细说明见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

---

## 目录结构

```
.
├── backend/                # Python 后端
│   ├── main.py             # FastAPI 入口
│   ├── api/                # 路由 + DTO
│   ├── agent/              # 任务调度 (6 个子工作流)
│   ├── services/           # 业务逻辑层
│   ├── repositories/       # 数据访问层
│   ├── models/             # SQLAlchemy ORM
│   ├── clients/            # 外部系统连接器
│   ├── core/               # 配置 / DB / 日志 / 异常
│   └── workers/            # Celery 异步任务
├── frontend/               # React + TypeScript SPA
├── deployment/             # Docker Compose + 监控
├── alembic/                # 数据库迁移
├── tests/                  # pytest 测试
├── docs/                   # 项目文档
├── pyproject.toml          # Python 依赖 (uv)
└── Makefile                # 开发命令集
```

---

## 测试

```bash
make test              # 全部测试
make test-unit         # 单元测试
make test-integration  # 集成测试 (需要基础设施)
make test-ui-mocked    # 前端 Playwright E2E
```

---

## 代码质量

```bash
make lint       # Ruff 检查
make format     # Ruff 格式化
make typecheck  # MyPy 类型检查
make hooks      # 安装 Git pre-commit hooks
```

---

## License

[GPL-3.0](LICENSE)
