# Skill 系统设计规范

> Agent 运行时的能力单元管理系统。将目标、策略、执行、接口打包为稳定可复用的模块，由 Supervisor 和 Workflow 按需调度。

---

## 一、核心概念：四层架构体系

系统分为四层，职责不重叠：

```
Supervisor (决策层)
  ├── Workflow (流程编排层)
  │     └── Skill (能力封装层)
  │           └── Tool (原子操作层)
  └── Skill (Supervisor 也可直接调用)
```

### 1. Tool — 原子动作

不可再分的最小操作单元。

示例：调 arXiv API、下载 PDF、调 reranker、写数据库、发消息到队列。

### 2. Skill — 面向局部目标的能力封装

一个 Skill 包含四层定义：

| 层         | 职责          | 示例（arxiv_search）                                |
| ---------- | ------------- | --------------------------------------------------- |
| **目标层** | 解决什么问题  | 找到相关论文，给出可信候选集                        |
| **策略层** | 如何完成      | query 扩展 → 时间窗过滤 → 去重 → rerank → 多维打分  |
| **执行层** | 依赖哪些 Tool | arXiv API、Semantic Scholar API、embedding/reranker |
| **接口层** | 输入输出形式  | 输入：topic, time_range, top_k → 输出：论文卡片列表 |

Skill 不是 Tool 的包装，也不是 mini-Workflow。它是一个 **自包含的能力单元**。

### 3. Workflow — 面向完整阶段目标的流程封装

包含多步状态推进、阶段切换、条件分支、异步任务管理、重试/回退/挂起/恢复、跨 Skill 上下文传递。

示例：Discovery、Extraction、Ideation、Execution、Critique、Publish。

### 4. Supervisor — 顶层决策器

负责任务分类、选择 Workflow 或直接调用 Skill、控制粒度、处理中断/升级/切换路径。

---

## 二、Skill 定义规范

### 目录结构

每个 Skill 是 `backend/agent/skills/` 下的独立目录：

```
backend/agent/skills/
├── __init__.py              # SkillRegistry 自动扫描入口
├── registry.py              # SkillRegistry 实现
├── base.py                  # SkillDefinition 数据结构 + 加载逻辑
│
├── arxiv_search/
│   ├── skill.yaml           # 声明文件
│   ├── execute.py           # 策略层 + 执行层 Python 实现
│   └── prompts/             # 可选：Skill 专用 prompt 模板
│       └── query_expand.yaml
│
├── pdf_to_markdown/
│   ├── skill.yaml
│   └── execute.py
│
└── ppt_generation/
    ├── skill.yaml
    └── execute.py
```

### skill.yaml 规范

YAML 声明 5 个字段 + 1 个模式字段：

```yaml
name: arxiv_search
description: "根据研究主题检索相关学术论文，返回结构化候选集与推荐理由"
mode: tool  # tool | subgraph

input_schema:
  topic:
    type: str
    required: true
    description: "研究主题或关键词"
  time_range:
    type: str
    required: false
    description: "时间范围，如 '2024-01-01:2025-03-01'"
  top_k:
    type: int
    required: false
    default: 10

output_schema:
  papers:
    type: list[PaperCard]
    description: "结构化论文卡片列表"
  recommendations:
    type: str
    description: "后续建议"

entrypoint: execute.run
```

**`mode` 字段说明**：

- `tool`：Skill 内部可有多步策略，但同步完成，暴露为 LangGraph `StructuredTool`
- `subgraph`：Skill 有多步状态推进、可能需要 HITL，暴露为 LangGraph `StateGraph`

---

## 三、SkillRegistry — 注册与加载

### 生命周期

```
应用启动
  │
  ▼
SkillRegistry.discover(skills_dir)
  │  扫描 skills/ 下所有 skill.yaml
  │
  ▼
解析 skill.yaml → SkillDefinition
  │
  ▼
动态导入 entrypoint 指向的 Python 函数
  │
  ▼
根据 mode 分路注册：
  ├─ tool     → 包装为 StructuredTool → 存入 registry.tools
  └─ subgraph → 存入 registry.subgraphs
```

### 核心 API

```python
class SkillRegistry:
    """启动时扫描 skills/ 目录，按 mode 分类注册所有 Skill。"""

    def discover(self, skills_dir: Path) -> None:
        """扫描目录，解析 skill.yaml，导入 entrypoint，注册。"""

    def get_tools(self) -> list[StructuredTool]:
        """返回所有 mode=tool 的 Skill，供 Supervisor bind_tools。"""

    def get_subgraph(self, name: str) -> StateGraph:
        """按名称获取 mode=subgraph 的 Skill，供 Workflow 嵌入。"""

    def list_skills(self) -> list[SkillDefinition]:
        """列出所有已注册 Skill 的元数据。"""
```

### Supervisor 消费方式

```python
# graph.py — 构建 Supervisor 时
registry = SkillRegistry()
registry.discover(Path("backend/agent/skills"))

# mode=tool 的 Skill 绑定给 Supervisor LLM
supervisor_llm = llm.bind_tools(
    registry.get_tools()          # Skill 工具
    + workflow_trigger_tools      # Workflow 触发工具
)

# mode=subgraph 的 Skill 在 Workflow 内部嵌入
# 例如 Publish Workflow 嵌入 ppt_generation subgraph
publish_graph.add_node("gen_ppt", registry.get_subgraph("ppt_generation"))
```

**设计决策**：
- 启动时一次性扫描注册，不做运行时热加载（YAGNI）
- Supervisor 同时持有 Tool 类型 Skill 和 Workflow 触发器，由 LLM 自行路由
- Subgraph 类型 Skill 由 Workflow 在构图时主动嵌入

---

## 四、首批 Skill 设计

### 1. arxiv_search

| 层       | 内容                                                                               |
| -------- | ---------------------------------------------------------------------------------- |
| **目标** | 找到与研究主题相关的高质量论文候选集                                               |
| **策略** | query 扩展（LLM 生成同义/相关术语）→ Arxiv API 检索 → 时间窗过滤 → 多维打分 → 排序 |
| **执行** | `arxiv_tool`（API 调用）、LLM（query 扩展 + 打分）                                 |
| **接口** | 输入：topic, time_range, top_k → 输出：`list[PaperCard]` + recommendations         |
| **mode** | `tool`                                                                             |

### 2. pdf_to_markdown

| 层       | 内容                                                                                     |
| -------- | ---------------------------------------------------------------------------------------- |
| **目标** | 将学术 PDF 转为结构完整的 Markdown（保留公式、表格、图注、引用关系）                     |
| **策略** | 调用 MinerU GPU 版面分析 → 段落/表格/公式分区识别 → 结构化 Markdown 组装 → 质量校验      |
| **执行** | `parser_engine`（MinerU 封装，services 层）                                              |
| **接口** | 输入：file_path 或 file_bytes → 输出：`MarkdownDocument`（含 sections, tables, figures） |
| **mode** | `tool`                                                                                   |

### 3. ppt_generation

| 层       | 内容                                                                                        |
| -------- | ------------------------------------------------------------------------------------------- |
| **目标** | 将结构化研究成果转为可直接使用的演示文稿                                                    |
| **策略** | 接收结构化内容 → LLM 生成分页大纲 → 逐页填充内容/图表 → Marp 或 python-pptx 渲染 → 输出文件 |
| **执行** | LLM（大纲 + 内容组织）、`python-pptx` 或 Marp CLI（渲染）                                   |
| **接口** | 输入：content_sections, template_style → 输出：`PPTArtifact`（文件路径 + 页面预览）         |
| **mode** | `subgraph`（多步状态推进，可能需要 HITL 确认大纲）                                          |

---

## 五、错误处理

### 错误类型

| 错误                         | 触发场景              | 处理方式                              |
| ---------------------------- | --------------------- | ------------------------------------- |
| `SkillNotFoundError`         | Registry 中无此 Skill | 直接抛出，Supervisor 感知             |
| `SkillExecutionError`        | Skill 运行时失败      | 携带 skill_name + 输入参数 + 原始异常 |
| `SkillSchemaValidationError` | 输入输出不符合 schema | 校验阶段拦截                          |

### 错误传播路径

```
mode: tool
  Skill 执行失败 → 抛出 SkillExecutionError
  → Supervisor LLM 收到错误信息
  → 自主决策：换参数重试 / 换 Skill / 上报用户

mode: subgraph
  节点内抛错 → Workflow 重试/回退机制处理
  → 超过重试上限 → SkillExecutionError 冒泡至 Supervisor
```

---

## 六、架构全景

```
┌──────────────────────────────────────────────────────┐
│                  Supervisor Agent                     │
│  意图识别 → 路由决策：                                │
│    ├─ 复杂任务 → 调 Workflow                          │
│    └─ 单项能力 → 直接调 Skill (tool)                  │
├──────────────────────────────────────────────────────┤
│              Workflow 层（6 个子图）                   │
│  Discovery / Extraction / Ideation / ...              │
│  内部可嵌入 Skill (subgraph)                          │
├──────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐│
│  │         SkillRegistry（启动时扫描注册）           ││
│  │  ┌──────────────┐ ┌───────────────┐ ┌──────────┐ ││
│  │  │ arxiv_search │ │pdf_to_markdown│ │ ppt_gen  │ ││
│  │  │   (tool)     │ │    (tool)     │ │(subgraph)│ ││
│  │  └──────┬───────┘ └──────┬───────┘ └────┬─────┘ ││
│  └─────────┼───────────────┼──────────────┼────────┘│
├────────────┼───────────────┼──────────────┼─────────┤
│            ▼               ▼              ▼         │
│                    Tool 层（原子操作）                │
│  arxiv_api / semantic_scholar / mineru / pptx_render  │
└──────────────────────────────────────────────────────┘
```
