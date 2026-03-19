# LangGraph Agent 详细设计

> Agent 运行时的核心设计：State 架构、Supervisor 路由、子图编排、跨 WF 数据传递与 Checkpoint 策略。

---

## 一、State 架构

### 1.1 设计决策

采用 **共享基座 + 私有扩展 + input/output schema 强制边界** 模式：

- `SharedState` 包含 4 个共享字段，所有图共用
- 每个 WF State 继承 `SharedState`，添加自己的私有字段
- 通过 LangGraph 的 `input` / `output` schema，WF 只接收和输出共享字段，私有字段不泄露

```
SupervisorState ──────────────── messages, plan, artifacts, ...
       │
       │  input=SharedState / output=SharedState
       │
  ┌────▼──────────────────────────────────────────────────┐
  │ DiscoveryState(SharedState)                           │
  │   + search_queries, raw_results, candidate_papers     │  ← 私有，外部不可见
  └───────────────────────────────────────────────────────┘
```

### 1.2 SharedState — 共享基座

所有图都能读写的 4 个字段。**永不扩充**——任何 WF 特有的数据走私有字段 + 产出物写 `artifacts`。

```python
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


def merge_dicts(left: dict, right: dict) -> dict:
    """合并字典，右侧覆盖左侧同名 key。"""
    merged = {**left}
    for key, value in right.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


class SharedState(TypedDict):
    """所有图的共享基座。只包含 4 个字段，永不扩充。"""

    messages: Annotated[list, add_messages]
    """对话历史。add_messages reducer 自动追加，不覆盖。"""

    workspace_id: str
    """当前 Workspace ID，用于租户隔离和 RAG 检索范围限定。"""

    discipline: str
    """学科领域（如 'computer_science'、'biology'），用于 Supervisor prompt 动态切换。"""

    artifacts: Annotated[dict, merge_dicts]
    """各 WF 产出物的汇总仓库。按 WF 命名空间隔离，merge_dicts reducer 深度合并。"""
```

### 1.3 SupervisorState — 主控状态

```python
from pydantic import BaseModel


class PlannedStep(BaseModel):
    """执行计划中的一步。"""
    workflow: str
    objective: str
    success_criteria: str


class ExecutionPlan(BaseModel):
    """Supervisor 输出的执行计划。"""
    steps: list[PlannedStep]
    goal: str


class SupervisorState(SharedState):
    """Supervisor 主控状态。继承 SharedState，添加规划与路由相关字段。"""

    plan: ExecutionPlan | None
    """当前执行计划。Pre-plan 模式下由 Supervisor 生成，每步完成后检查点回评。"""

    current_step_index: int
    """当前执行到计划的第几步（0-indexed）。"""

    routing_decision: str | None
    """最近一次路由决策的目标 WF 名称。用于条件边判断。"""
```

### 1.4 各 Workflow State 定义

#### DiscoveryState — 寻源初筛

```python
class PaperCard(BaseModel):
    """论文卡片：检索结果的结构化表示。"""
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    year: int
    citation_count: int | None = None
    relevance_score: float
    relevance_comment: str
    """LLM 基于 abstract 生成的一句话相关性评语，供用户 HITL 勾选时参考。"""
    source: str  # "arxiv" | "semantic_scholar" | "pubmed"


class DiscoveryState(SharedState):
    """寻源初筛：从关键词/主题出发，检索并筛选候选论文集。"""

    search_queries: list[str]
    """LLM 扩展后的搜索查询列表。"""

    raw_results: list[dict]
    """API 原始返回（未过滤）。"""

    candidate_papers: list[PaperCard]
    """过滤、排序、去重后的候选集。"""

    selected_paper_ids: list[str]
    """用户 HITL 勾选的论文 ID 列表。"""

    ingestion_task_ids: list[str]
    """对选中论文触发的 Celery ingestion 任务 ID，供 Extraction 轮询用。"""
```

#### ExtractionState — 深度精读

```python
class ReadingNote(BaseModel):
    """单篇论文的精读笔记。"""
    paper_id: str
    key_contributions: list[str]
    methodology: str
    experimental_setup: str
    main_results: str
    limitations: list[str]
    source_chunks: list[str]  # RAG 召回的原文段落 ID，用于溯源


class ComparisonEntry(BaseModel):
    """跨文献对比矩阵的一行。"""
    paper_id: str
    method: str
    dataset: str
    metric_values: dict[str, float]
    key_difference: str


class ExtractionState(SharedState):
    """深度精读：定向 RAG 召回关键段落，跨文档对比，构建术语表。"""

    paper_ids: list[str]
    """待精读的论文 ID 列表（从 artifacts["discovery"]["papers"] 获取）。"""

    reading_notes: list[ReadingNote]
    """逐篇精读笔记。"""

    comparison_matrix: list[ComparisonEntry]
    """跨文献方法论对比矩阵。"""

    glossary: dict[str, str]
    """专业术语表 {术语: 定义}。"""
```

#### IdeationState — 实验推演

```python
class ResearchGap(BaseModel):
    """识别出的 Research Gap。"""
    description: str
    supporting_evidence: list[str]
    potential_impact: str


class ExperimentDesign(BaseModel):
    """实验方案设计。"""
    hypothesis: str
    method_description: str
    baselines: list[str]
    datasets: list[str]
    evaluation_metrics: list[str]
    expected_outcome: str


class IdeationState(SharedState):
    """实验推演：识别 Research Gap，设计实验方案和评估体系。"""

    research_gaps: list[ResearchGap]
    """从精读笔记中识别出的研究空白。"""

    experiment_designs: list[ExperimentDesign]
    """针对 Gap 提出的实验方案。"""

    selected_design_index: int | None
    """用户/LLM 选定的方案索引。"""
```

#### ExecutionState — 沙盒验证

```python
class ExecutionResult(BaseModel):
    """沙盒执行结果。"""
    exit_code: int
    stdout: str
    stderr: str
    output_files: list[str]  # 生成的图表/数据文件路径
    execution_time_seconds: float


class ExecutionState(SharedState):
    """沙盒验证：代码生成、HITL 确认、Docker 隔离执行、Debug 重试。"""

    task_description: str
    """代码任务描述（来自 Ideation 方案或用户直接指令）。"""

    generated_code: str
    """LLM 生成的 Python 代码。"""

    execution_result: ExecutionResult | None
    """最近一次执行结果。"""

    retry_count: int
    """已重试次数。硬上限 3。"""

    reflection: str | None
    """失败后的 LLM 反思分析（用于下次代码生成）。"""

    elapsed_seconds: float
    """累计执行耗时（时间预算检查用）。"""

    tokens_used: int
    """累计消耗 token 数（token 预算检查用）。"""
```

#### CritiqueState — 模拟审稿

```python
class CritiqueFeedback(BaseModel):
    """结构化审稿意见。"""
    category: str  # "logic" | "data" | "citation" | "methodology" | "writing"
    severity: str  # "critical" | "major" | "minor"
    description: str
    suggestion: str
    location: str | None = None  # 指向 artifacts 中的具体位置


class CritiqueState(SharedState):
    """模拟审稿：红蓝对抗审查、逻辑检测、structured feedback。"""

    target_workflow: str
    """审查目标 WF 名称（如 "extraction"、"ideation"）。"""

    supporter_opinion: str
    """支持者（蓝方）的正面评价。"""

    critic_opinion: str
    """批评者（红方）的质疑和问题。"""

    feedbacks: list[CritiqueFeedback]
    """结构化审稿意见列表。"""

    verdict: str
    """裁决结果："pass" | "revise"。由裁决节点填入。"""

    critique_round: int
    """当前审稿轮次。硬上限 2。"""
```

#### PublishState — 报告交付

```python
class OutlineSection(BaseModel):
    """报告大纲的一个章节。"""
    title: str
    description: str
    source_artifacts: list[str]  # 引用的 artifacts 路径


class PublishState(SharedState):
    """报告交付：大纲组装、Markdown 生成、PPTX 渲染、ZIP 打包。"""

    outline: list[OutlineSection]
    """报告大纲。"""

    markdown_content: str
    """生成的 Markdown 报告全文。"""

    citation_map: dict[str, str]
    """引用映射 {角标编号: 论文信息}。"""

    output_files: list[str]
    """最终产物文件路径列表（.md, .pptx, .zip）。"""
```

### 1.5 State 数据流全景

```
用户消息                          SharedState.artifacts 变化
   │
   ▼
SupervisorState
   │  plan: [discovery, extraction, ideation]
   │
   ├──► DiscoveryState
   │    input: SharedState (messages, workspace_id, discipline, artifacts={})
   │    私有: search_queries, raw_results, candidate_papers
   │    output: SharedState (artifacts={"discovery": {"papers": [...]}})
   │
   ├──► ExtractionState
   │    input: SharedState (artifacts={"discovery": {...}})     ← 自动拿到上游产出
   │    私有: paper_ids, reading_notes, comparison_matrix, glossary
   │    output: SharedState (artifacts={"discovery":..., "extraction": {"notes":..., "matrix":..., "glossary":...}})
   │
   ├──► IdeationState
   │    input: SharedState (artifacts={"discovery":..., "extraction":...})
   │    私有: research_gaps, experiment_designs, selected_design_index
   │    output: SharedState (artifacts={..., "ideation": {"gaps":..., "design":...}})
   │
   └──► ...后续 WF 同理
```

---

## 二、Supervisor 路由策略

### 2.1 设计决策

采用 **硬规则门禁/直达 + LLM 结构化输出** 的混合路由模式：

- 少量明确模式走硬规则，零延迟直达目标 WF
- 其余走 LLM 结构化输出，用 `RouteDecision` 模型约束输出格式
- 规划模式采用 **Pre-plan + 检查点回评**：先输出完整计划，每步完成后轻量检查是否继续

### 2.2 硬规则门禁

在进入 LLM 路由前，先过一层确定性规则。匹配即直达，不消耗 LLM token。

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class HardRule:
    """硬规则：模式匹配 → 直达目标 WF。"""
    name: str
    match: Callable[[list], bool]  # 接收 messages，返回是否匹配
    target: str                     # 目标 WF 名称


HARD_RULES: list[HardRule] = [
    HardRule(
        name="code_execution_direct",
        match=lambda msgs: _last_human_has_code_block(msgs),
        target="execution",
    ),
    HardRule(
        name="file_upload_trigger",
        match=lambda msgs: _last_message_has_attachment(msgs),
        target="discovery",
    ),
]


def apply_hard_rules(messages: list) -> str | None:
    """按序检查硬规则，首个匹配即返回目标 WF。无匹配返回 None。"""
    for rule in HARD_RULES:
        if rule.match(messages):
            return rule.target
    return None
```

**规则设计原则**：

- 只用于**零歧义**的直达场景（用户贴了代码块、上传了文件）
- 数量控制在 5 条以内，多了就用 LLM
- 每条规则必须有 `name` 字段，用于日志追踪和可观测性（日志规范详见 [可观测性设计](2026-03-19-observability-design.md)）

### 2.3 LLM 结构化输出路由

硬规则未匹配时，走 LLM 路由。LLM 输出结构化的 `RouteDecision`：

```python
class RouteDecision(BaseModel):
    """Supervisor LLM 的路由决策输出。"""

    mode: Literal["single", "plan"]
    """路由模式。single = 单步直达，plan = 多步计划。"""

    target_workflow: str | None = None
    """mode=single 时，目标 WF 名称。"""

    plan: ExecutionPlan | None = None
    """mode=plan 时，完整执行计划。"""

    reasoning: str
    """决策理由（可观测性：写入日志 + 前端 CoT 展示）。"""
```

Supervisor 节点实现：

```python
def supervisor_node(state: SupervisorState) -> dict:
    """Supervisor 主控节点：硬规则 → LLM 路由 → 更新 State。"""

    # 1. 硬规则检查
    hard_target = apply_hard_rules(state["messages"])
    if hard_target:
        return {
            "routing_decision": hard_target,
            "plan": None,
            "current_step_index": 0,
        }

    # 2. LLM 结构化输出路由
    decision = llm.with_structured_output(RouteDecision).invoke(
        [system_prompt(state["discipline"])] + state["messages"]
    )

    if decision.mode == "single":
        return {
            "routing_decision": decision.target_workflow,
            "plan": None,
            "current_step_index": 0,
        }

    # mode == "plan"
    # 提取用户研究方向到 artifacts["supervisor"]，供 Ideation 等下游 WF 使用
    return {
        "routing_decision": decision.plan.steps[0].workflow,
        "plan": decision.plan,
        "current_step_index": 0,
        "artifacts": {
            "supervisor": {
                "research_direction": decision.reasoning,  # 从 LLM 推理中提取
                "goal": decision.plan.goal,
            }
        },
    }
```

### 2.4 Pre-plan + 检查点回评

多步计划模式下，每个 WF 执行完后经过一个轻量的**检查点回评节点**，决定是否继续原计划：

```python
def checkpoint_evaluator(state: SupervisorState) -> dict:
    """检查点回评：验证当前步骤结果是否支持继续原计划。"""
    plan = state["plan"]
    step_index = state["current_step_index"]
    current_step = plan.steps[step_index]

    # 检查 success_criteria 是否满足
    evaluation = llm.with_structured_output(StepEvaluation).invoke([
        SystemMessage(content="评估当前步骤是否达到预期目标。"),
        HumanMessage(content=f"""
步骤目标: {current_step.objective}
成功标准: {current_step.success_criteria}
当前 artifacts: {json.dumps(state['artifacts'], ensure_ascii=False)}
"""),
    ])

    if evaluation.passed:
        # 继续下一步
        next_index = step_index + 1
        if next_index >= len(plan.steps):
            return {"routing_decision": "__end__", "current_step_index": next_index}
        return {
            "routing_decision": plan.steps[next_index].workflow,
            "current_step_index": next_index,
        }
    else:
        # 不通过 → 回到 Supervisor 重新规划
        return {"routing_decision": "__replan__", "plan": None}


class StepEvaluation(BaseModel):
    """检查点回评结果。"""
    passed: bool
    reason: str
    suggestion: str | None = None
```

### 2.5 Supervisor 主图编排

```python
from langgraph.graph import StateGraph, START, END

def build_supervisor_graph() -> StateGraph:
    graph = StateGraph(SupervisorState)

    # ── 节点注册 ──
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("checkpoint_eval", checkpoint_evaluator)

    # 6 个 WF 作为 subgraph 节点
    graph.add_node("discovery", discovery_subgraph)
    graph.add_node("extraction", extraction_subgraph)
    graph.add_node("ideation", ideation_subgraph)
    graph.add_node("execution", execution_subgraph)
    graph.add_node("critique", critique_subgraph)
    graph.add_node("publish", publish_subgraph)

    # ── 边连接 ──
    graph.add_edge(START, "supervisor")

    # Supervisor → 路由到目标 WF
    graph.add_conditional_edges("supervisor", route_to_workflow, [
        "discovery", "extraction", "ideation",
        "execution", "critique", "publish", END,
    ])

    # 每个 WF 完成 → 检查点回评
    for wf in ["discovery", "extraction", "ideation",
               "execution", "critique", "publish"]:
        graph.add_edge(wf, "checkpoint_eval")

    # 检查点回评 → 继续下一步 / 回到 Supervisor 重新规划 / 结束
    graph.add_conditional_edges("checkpoint_eval", route_after_eval, [
        "discovery", "extraction", "ideation",
        "execution", "critique", "publish",
        "supervisor",  # __replan__
        END,           # __end__
    ])

    return graph.compile(checkpointer=PostgresSaver(...))


def route_to_workflow(state: SupervisorState) -> str:
    """根据 routing_decision 路由到目标 WF。"""
    decision = state["routing_decision"]
    if decision is None:
        return END
    return decision


def route_after_eval(state: SupervisorState) -> str:
    """检查点回评后的路由。"""
    decision = state["routing_decision"]
    if decision == "__end__":
        return END
    if decision == "__replan__":
        return "supervisor"
    return decision
```

### 2.6 Supervisor 主图可视化

```
                         ┌───────────┐
                   ┌────►│    END    │
                   │     └───────────┘
                   │
┌───────┐    ┌─────┴──────┐    ┌──────────────────┐
│ START │───►│ supervisor │───►│ discovery        │──┐
└───────┘    └─────┬──────┘    ├──────────────────┤  │
                   │           │ extraction       │──┤
                   │           ├──────────────────┤  │
                   │           │ ideation         │──┤   ┌──────────────────┐
                   │           ├──────────────────┤  ├──►│ checkpoint_eval  │
                   │           │ execution        │──┤   │ (检查点回评)      │
                   │           ├──────────────────┤  │   └────┬────┬────────┘
                   │           │ critique         │──┤        │    │
                   │           ├──────────────────┤  │        │    │ __replan__
                   │           │ publish          │──┘        │    └──► supervisor
                   │           └──────────────────┘           │
                   │                                          │ __end__
                   │                                          ▼
                   └──────────────────────────────────────► END
```

---

## 三、子图编排细节

### 3.1 编排原则

| 原则                 | 说明                                                            |
| -------------------- | --------------------------------------------------------------- |
| **确定性条件边优先** | WF 内部分支尽量检查 State 字段值，不调 LLM                      |
| **语义判断用 LLM**   | 仅在需要理解内容含义时用 LLM（如 Critique 裁决）                |
| **四重循环保障**     | ① 计数器硬上限 ② 条件边检查 ③ 时间/Token 预算 ④ recursion_limit |
| **独立 HITL 节点**   | interrupt 放在独立节点，单一职责，不与业务逻辑混合              |

### 3.2 循环退出保障机制

所有含循环的 WF 统一使用此检查函数：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class LoopBudget:
    """循环预算配置。"""
    max_retries: int
    max_elapsed_seconds: float
    max_tokens: int


# 各 WF 的预算配置
EXECUTION_BUDGET = LoopBudget(max_retries=3, max_elapsed_seconds=300.0, max_tokens=50000)
CRITIQUE_BUDGET = LoopBudget(max_retries=2, max_elapsed_seconds=180.0, max_tokens=30000)


def check_loop_budget(
    retry_count: int,
    elapsed_seconds: float,
    tokens_used: int,
    budget: LoopBudget,
) -> str | None:
    """检查循环预算是否超限。返回退出原因字符串，未超限返回 None。"""
    if retry_count >= budget.max_retries:
        return f"max_retries_exceeded ({retry_count}/{budget.max_retries})"
    if elapsed_seconds >= budget.max_elapsed_seconds:
        return f"time_budget_exceeded ({elapsed_seconds:.0f}s/{budget.max_elapsed_seconds:.0f}s)"
    if tokens_used >= budget.max_tokens:
        return f"token_budget_exceeded ({tokens_used}/{budget.max_tokens})"
    return None
```

### 3.3 各 WF 内部节点编排

#### Discovery — 寻源初筛

```
START → expand_query → search_apis → filter_and_rank → present_candidates → trigger_ingestion → write_artifacts → END
                                                        (HITL: 用户勾选论文)
```

含 HITL：用户在 `present_candidates` 节点勾选要深读的论文，仅对选中论文触发 ingestion。

```python
discovery_graph = StateGraph(DiscoveryState, input=SharedState, output=SharedState)

discovery_graph.add_node("expand_query", expand_query)               # LLM 扩展查询词
discovery_graph.add_node("search_apis", search_apis)                 # 调 Arxiv/Semantic Scholar
discovery_graph.add_node("filter_and_rank", filter_and_rank)         # 去重 + 多维打分 + LLM 相关性评语
discovery_graph.add_node("present_candidates", present_candidates)   # HITL: 展示候选列表，用户勾选
discovery_graph.add_node("trigger_ingestion", trigger_ingestion)     # 对选中论文触发 BFF document service ingestion
discovery_graph.add_node("write_artifacts", write_artifacts)         # 写入 artifacts["discovery"]

discovery_graph.add_edge(START, "expand_query")
discovery_graph.add_edge("expand_query", "search_apis")
discovery_graph.add_edge("search_apis", "filter_and_rank")
discovery_graph.add_edge("filter_and_rank", "present_candidates")
discovery_graph.add_edge("present_candidates", "trigger_ingestion")
discovery_graph.add_edge("trigger_ingestion", "write_artifacts")
discovery_graph.add_edge("write_artifacts", END)


def present_candidates(state: DiscoveryState) -> dict:
    """独立 HITL 节点：展示候选论文列表（abstract + 相关性评语），用户勾选要深读的论文。"""
    response = interrupt({
        "action": "select_papers",
        "candidates": [
            {"id": p.arxiv_id, "title": p.title, "abstract": p.abstract,
             "year": p.year, "relevance_score": p.relevance_score,
             "relevance_comment": p.relevance_comment}
            for p in state["candidate_papers"]
        ],
    })
    return {"selected_paper_ids": response["selected_ids"]}
```

#### Extraction — 深度精读

```
START → wait_rag_ready → retrieve_chunks → generate_notes → cross_compare → build_glossary → write_artifacts → END
```

线性流程。`wait_rag_ready` 轮询等待 RAG Pipeline 解析完成。

```python
extraction_graph = StateGraph(ExtractionState, input=SharedState, output=SharedState)

extraction_graph.add_node("wait_rag_ready", wait_rag_ready)       # 轮询文档解析状态
extraction_graph.add_node("retrieve_chunks", retrieve_chunks)     # 定向 RAG 召回
extraction_graph.add_node("generate_notes", generate_notes)       # LLM 生成精读笔记
extraction_graph.add_node("cross_compare", cross_compare)         # LLM 跨文档对比
extraction_graph.add_node("build_glossary", build_glossary)       # LLM 术语表构建
extraction_graph.add_node("write_artifacts", write_artifacts)

extraction_graph.add_edge(START, "wait_rag_ready")
extraction_graph.add_edge("wait_rag_ready", "retrieve_chunks")
extraction_graph.add_edge("retrieve_chunks", "generate_notes")
extraction_graph.add_edge("generate_notes", "cross_compare")
extraction_graph.add_edge("cross_compare", "build_glossary")
extraction_graph.add_edge("build_glossary", "write_artifacts")
extraction_graph.add_edge("write_artifacts", END)
```

#### Ideation — 实验推演

```
START → analyze_gaps → generate_designs → select_design → write_artifacts → END
```

线性流程。

```python
ideation_graph = StateGraph(IdeationState, input=SharedState, output=SharedState)

ideation_graph.add_node("analyze_gaps", analyze_gaps)           # LLM 分析 Research Gap
ideation_graph.add_node("generate_designs", generate_designs)   # LLM 生成实验方案
ideation_graph.add_node("select_design", select_design)         # LLM 推荐 + 排序
ideation_graph.add_node("write_artifacts", write_artifacts)

ideation_graph.add_edge(START, "analyze_gaps")
ideation_graph.add_edge("analyze_gaps", "generate_designs")
ideation_graph.add_edge("generate_designs", "select_design")
ideation_graph.add_edge("select_design", "write_artifacts")
ideation_graph.add_edge("write_artifacts", END)
```

#### Execution — 沙盒验证（含循环 + HITL）

```
                    ┌──────────────── budget_exceeded ──────────────┐
                    │                                               ▼
START → generate_code → request_confirmation → execute_sandbox → check_result
                              (HITL interrupt)        │               │
                                                      │         success │ failure
                                                      │               ▼
                                                      │          reflect_and_retry ──→ generate_code
                                                      │
                                                      └──→ write_artifacts → END
```

```python
execution_graph = StateGraph(ExecutionState, input=SharedState, output=SharedState)

execution_graph.add_node("generate_code", generate_code)
execution_graph.add_node("request_confirmation", request_confirmation)  # HITL
execution_graph.add_node("execute_sandbox", execute_sandbox)
execution_graph.add_node("check_result", check_result)
execution_graph.add_node("reflect_and_retry", reflect_and_retry)
execution_graph.add_node("write_artifacts", write_artifacts)

execution_graph.add_edge(START, "generate_code")
execution_graph.add_edge("generate_code", "request_confirmation")
execution_graph.add_edge("request_confirmation", "execute_sandbox")

# check_result: 确定性条件边
execution_graph.add_conditional_edges("execute_sandbox", route_execution_result, [
    "write_artifacts",      # exit_code == 0
    "reflect_and_retry",    # exit_code != 0 且预算未超
    "write_artifacts",      # 预算超限，带失败标记写入
])

execution_graph.add_edge("reflect_and_retry", "generate_code")  # 循环回去
execution_graph.add_edge("write_artifacts", END)


def route_execution_result(state: ExecutionState) -> str:
    """确定性路由：检查执行结果和预算。"""
    if state["execution_result"].exit_code == 0:
        return "write_artifacts"

    budget_reason = check_loop_budget(
        state["retry_count"], state["elapsed_seconds"],
        state["tokens_used"], EXECUTION_BUDGET,
    )
    if budget_reason:
        return "write_artifacts"  # 预算超限，带失败标记退出

    return "reflect_and_retry"


def request_confirmation(state: ExecutionState) -> dict:
    """独立 HITL 节点：展示代码，等待用户确认执行。"""
    interrupt({
        "action": "confirm_execute",
        "code": state["generated_code"],
        "task": state["task_description"],
    })
    return {}
```

#### Critique — 模拟审稿

```
START ─┬─ supporter_review ─┬─ judge_verdict → write_artifacts → END
      └─ critic_review ───┘
      (并行，互不可见)    (合并后裁决)
```

Critique WF 自身不做"打回重调上游"的循环。只输出 `verdict` 和 `feedbacks` 到 artifacts。**打回逻辑由 Supervisor 的检查点回评处理**——回评节点看到 `verdict=revise` 后，将 feedback 注入 messages，重新调度上游 WF。

**supporter 和 critic 并行执行，互不可见**，避免锚定效应。两方都只看原始产出物，独立给出意见后由 judge 合并裁决。

```python
from langgraph.constants import Send

critique_graph = StateGraph(CritiqueState, input=SharedState, output=SharedState)

critique_graph.add_node("supporter_review", supporter_review)   # 蓝方正面评价
critique_graph.add_node("critic_review", critic_review)         # 红方质疑
critique_graph.add_node("judge_verdict", judge_verdict)         # 裁决节点（LLM 语义判断）
critique_graph.add_node("write_artifacts", write_artifacts)

# 并行 fan-out：START 同时发送到 supporter 和 critic
def fan_out_reviews(state: CritiqueState) -> list[Send]:
    """Supporter 和 Critic 并行执行，互不可见。"""
    return [
        Send("supporter_review", state),
        Send("critic_review", state),
    ]

critique_graph.add_conditional_edges(START, fan_out_reviews)
critique_graph.add_edge("supporter_review", "judge_verdict")
critique_graph.add_edge("critic_review", "judge_verdict")
critique_graph.add_edge("judge_verdict", "write_artifacts")
critique_graph.add_edge("write_artifacts", END)
```

#### Publish — 报告交付（含 HITL）

```
                                            ┌─── reject ──→ 推送 Canvas 用户手改 ──→ 确认定稿 ──┐
                                            │                                              │
START → assemble_outline → generate_markdown → request_finalization ──────────────────┤
                                            │                                              │
                                            └─── approve ──────────────────────────────┘
                                                                                           │
                                                                                           ▼
                                                                    render_pptx → package_zip → write_artifacts → END
```

```python
publish_graph = StateGraph(PublishState, input=SharedState, output=SharedState)

publish_graph.add_node("assemble_outline", assemble_outline)
publish_graph.add_node("generate_markdown", generate_markdown)
publish_graph.add_node("request_finalization", request_finalization)  # HITL
publish_graph.add_node("render_pptx", render_pptx)
publish_graph.add_node("package_zip", package_zip)
publish_graph.add_node("write_artifacts", write_artifacts)

publish_graph.add_edge(START, "assemble_outline")
publish_graph.add_edge("assemble_outline", "generate_markdown")
publish_graph.add_edge("generate_markdown", "request_finalization")
publish_graph.add_edge("request_finalization", "render_pptx")
publish_graph.add_edge("render_pptx", "package_zip")
publish_graph.add_edge("package_zip", "write_artifacts")
publish_graph.add_edge("write_artifacts", END)


def request_finalization(state: PublishState) -> dict:
    """独立 HITL 节点：展示 Markdown 报告，用户可 approve 或 reject。
    reject 时 Markdown 推送至 Canvas 编辑器，用户手改完确认后回流。
    """
    response = interrupt({
        "action": "confirm_finalize",
        "markdown_preview": state["markdown_content"][:2000],
        "outline": [s.title for s in state["outline"]],
    })
    # response: {"decision": "approve"} 或 {"decision": "approve", "modified_markdown": "..."}
    # reject 场景：前端将 markdown 推送到 Canvas，用户编辑完成后点击"确认定稿"按钮，
    # 前端将修改后的 markdown 作为 modified_markdown 发送 resume。
    if response.get("modified_markdown"):
        return {"markdown_content": response["modified_markdown"]}
    return {}
```

---

## 四、跨 WF 数据传递

### 4.1 设计决策

- `artifacts` 按 **WF 命名空间**隔离，天然避免 key 冲突
- WF 产出物通过 `artifacts` 在共享层自动流转，Supervisor 不做数据搬运
- Critique 打回重做时，feedback 通过 **messages 注入**传递，上游 WF 无需感知 Critique 的存在

### 4.2 artifacts 命名空间约定

每个 WF 只写入自己命名空间下的 key。`merge_dicts` reducer 保证深度合并，后写覆盖先写。

```python
# 各 WF 的 write_artifacts 节点统一模式
def write_artifacts_discovery(state: DiscoveryState) -> dict:
    """将 Discovery 产出物写入 artifacts 命名空间。"""
    return {
        "artifacts": {
            "discovery": {
                "papers": [p.model_dump() for p in state["candidate_papers"]],
                "selected_paper_ids": state["selected_paper_ids"],
                "ingestion_task_ids": state["ingestion_task_ids"],
                "search_metadata": {
                    "queries": state["search_queries"],
                    "total_raw_results": len(state["raw_results"]),
                },
            }
        }
    }


def write_artifacts_extraction(state: ExtractionState) -> dict:
    """将 Extraction 产出物写入 artifacts 命名空间。"""
    return {
        "artifacts": {
            "extraction": {
                "reading_notes": [n.model_dump() for n in state["reading_notes"]],
                "comparison_matrix": [e.model_dump() for e in state["comparison_matrix"]],
                "glossary": state["glossary"],
            }
        }
    }


# 其余 WF 同理：ideation, execution, critique, publish
```

**命名空间完整列表**：

| 命名空间                  | 写入者        | 核心 key                                                   | 消费者                       |
| ------------------------- | ------------- | ---------------------------------------------------------- | ---------------------------- |
| `artifacts["supervisor"]` | Supervisor    | `research_direction`, `key_constraints`                    | Ideation                     |
| `artifacts["discovery"]`  | Discovery WF  | `papers`, `selected_paper_ids`, `ingestion_task_ids`       | Extraction, Supervisor       |
| `artifacts["extraction"]` | Extraction WF | `reading_notes`, `comparison_matrix`, `glossary`           | Ideation, Critique, Publish  |
| `artifacts["ideation"]`   | Ideation WF   | `research_gaps`, `experiment_design`, `evaluation_metrics` | Execution, Critique, Publish |
| `artifacts["execution"]`  | Execution WF  | `code`, `results`, `output_files`                          | Critique, Publish            |
| `artifacts["critique"]`   | Critique WF   | `{target_wf: {verdict, feedbacks, round}}`                 | Supervisor (检查点回评)      |
| `artifacts["publish"]`    | Publish WF    | `markdown`, `pptx_path`, `zip_path`                        | 前端展示                     |

### 4.3 Critique 打回 — messages 注入机制

Critique 产出 `verdict=revise` 后，打回逻辑由 Supervisor 的检查点回评节点处理：

```python
def checkpoint_evaluator(state: SupervisorState) -> dict:
    """检查点回评：含 Critique 打回处理。"""
    plan = state["plan"]
    step_index = state["current_step_index"]
    current_step = plan.steps[step_index]

    # 特殊处理：Critique WF 完成后，检查对应 target 的审查结果
    critique_results = state["artifacts"].get("critique", {})
    # Critique artifacts 按 target 做二级命名空间：{"extraction": {verdict, feedbacks, round}, ...}
    for target_wf, result in critique_results.items():
        if result.get("verdict") == "revise":
            feedbacks = result["feedbacks"]

            # 构造修改指令注入 messages
            feedback_text = "\n".join(
                f"- [{fb['severity']}] {fb['category']}: {fb['description']} → {fb['suggestion']}"
                for fb in feedbacks
            )
            revision_message = HumanMessage(content=f"""
根据模拟审稿意见，请修改 {target_wf} 阶段的产出物。需要修正的问题：

{feedback_text}

请基于以上反馈重新执行 {target_wf} 阶段。
""")

            return {
                "messages": [revision_message],
                "routing_decision": target_wf,
                "plan": None,  # 打回后取消原计划，由 Supervisor 重新规划
            }

    # 正常流程：检查 success_criteria
    # ... (同 2.4 节逻辑)
```

### 4.4 完整数据流示例

以 `Discovery → Extraction → Critique → 打回 Extraction → 再 Critique → Publish` 为例：

```
步骤 1: Discovery 完成
─────────────────────
SharedState.artifacts = {
    "discovery": {
        "papers": [{"arxiv_id": "2401.xxxxx", "title": "...", ...}, ...],
        "search_metadata": {"queries": ["transformer attention"], "total_raw_results": 47}
    }
}

步骤 2: Extraction 完成
─────────────────────
SharedState.artifacts = {
    "discovery": { ... },                          ← 保持不变
    "extraction": {
        "reading_notes": [{"paper_id": "2401.xxxxx", "key_contributions": [...], ...}],
        "comparison_matrix": [{"paper_id": "...", "method": "...", ...}],
        "glossary": {"Attention": "注意力机制是...", "MHA": "多头注意力..."}
    }
}

步骤 3: Critique 完成 (verdict=revise)
─────────────────────
SharedState.artifacts = {
    "discovery": { ... },
    "extraction": { ... },
    "critique": {
        "target": "extraction",
        "verdict": "revise",
        "feedbacks": [
            {"category": "methodology", "severity": "major",
             "description": "论文 A 和 B 的对比缺少消融实验维度",
             "suggestion": "补充 ablation study 相关对比列"}
        ]
    }
}

步骤 4: checkpoint_evaluator 看到 verdict=revise
─────────────────────
→ 构造 HumanMessage: "根据审稿意见，请修改 extraction 阶段..."
→ routing_decision = "extraction"
→ Extraction WF 重新执行（messages 里多了修改指令）

步骤 5: Extraction 重做完成
─────────────────────
SharedState.artifacts = {
    "discovery": { ... },
    "extraction": {                                ← merge_dicts 覆盖旧版
        "reading_notes": [更新版],
        "comparison_matrix": [更新版，含 ablation 维度],
        "glossary": {更新版}
    },
    "critique": { ... }                            ← 旧 critique 结果仍在
}

步骤 6: 再过 Critique (verdict=pass)
─────────────────────
SharedState.artifacts = {
    ...,
    "critique": {
        "target": "extraction",
        "verdict": "pass",                         ← 覆盖为 pass
        "feedbacks": []
    }
}

步骤 7: Publish 读取所有 artifacts 生成报告
```

---

## 五、Checkpoint 策略

### 5.1 设计决策

| 决策项          | 选择                 | 理由                                           |
| --------------- | -------------------- | ---------------------------------------------- |
| Checkpoint 范围 | **全量默认**         | PostgresSaver 每节点自动 checkpoint，零配置    |
| Thread 恢复粒度 | **自动恢复最新**     | MVP 只支持从最新 checkpoint 继续，回滚后续迭代 |
| Checkpoint 清理 | **MVP 不做自动清理** | YAGNI，监控存储用量，手动处理                  |

### 5.2 Checkpointer 配置

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def build_checkpointer(db_url: str) -> AsyncPostgresSaver:
    """创建 PostgreSQL Checkpointer。"""
    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
    await checkpointer.setup()  # 自动创建 checkpoint 表
    return checkpointer


# 编译主图时注入
checkpointer = await build_checkpointer(settings.database_url)
app = build_supervisor_graph().compile(checkpointer=checkpointer)
```

### 5.3 Checkpoint 存储内容

每次 checkpoint 存储的是 `SupervisorState`（因为 WF subgraph 的 output=SharedState，私有字段被过滤）：

```
Checkpoint 内容 = SupervisorState = SharedState + plan + current_step_index + routing_decision

具体字段大小估算：
├── messages: 对话历史（主要体积，随对话增长）
├── workspace_id: 固定 36 bytes
├── discipline: 固定 ~20 bytes
├── artifacts: 各 WF 产出物（随流程推进增长）
├── plan: ExecutionPlan JSON（~500 bytes）
├── current_step_index: 4 bytes
└── routing_decision: ~20 bytes
```

### 5.4 Thread 恢复流程

```
用户关闭浏览器 → 重新打开 → 选择之前的 Thread
                                    │
                                    ▼
                    前端: GET /agent/threads/{id}
                                    │
                                    ▼
                    BFF: 查本地 DB thread status
                         ├── active → 返回 thread 详情
                         └── 查 LangGraph 获取最新 state
                                    │
                                    ▼
                    前端: 展示之前的对话历史（从 messages 恢复）
                    前端: 展示之前的产出物（从 artifacts 恢复）
                                    │
                                    ▼
                    用户发送新消息 → POST /agent/threads/{id}/runs
                                    │
                                    ▼
                    LangGraph: 自动加载最新 checkpoint
                              从 Supervisor 节点继续执行
```

### 5.5 HITL 中断恢复

HITL interrupt 是 checkpoint 的核心应用场景。流程如下：

```
Execution WF 的 request_confirmation 节点
    │
    ▼ interrupt({code, action})
    │
    ▼ LangGraph 自动 checkpoint 当前状态
    │
    ▼ 前端收到 interrupt SSE 事件，展示确认卡片
    │
    ... (用户可能离开，数小时后回来)
    │
    ▼ 用户点击"确认执行"
    │
    ▼ 前端: POST /agent/threads/{id}/runs/{run_id}/resume
    │       body: {action: "approve"}
    │
    ▼ BFF: AgentService.resume_run()
    │       → 创建 run_snapshot (parent_run_id = old_run_id)
    │       → LangGraph client.runs.create(command=Command(resume={action: "approve"}))
    │
    ▼ LangGraph: 从 checkpoint 恢复
    │            → request_confirmation 节点返回
    │            → 继续执行 execute_sandbox 节点
```

### 5.6 LangGraph recursion_limit 兜底

作为循环保障的最后一道防线，编译图时设置全局 `recursion_limit`：

```python
app = build_supervisor_graph().compile(
    checkpointer=checkpointer,
)

# 调用时传入 config
result = await app.ainvoke(
    input_state,
    config={
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,  # 全局节点执行上限
    },
)
```

**recursion_limit 的取值逻辑**：

```
最长合理路径估算:
  Supervisor(1) + Discovery(4) + checkpoint_eval(1)
  + Supervisor(1) + Extraction(6) + checkpoint_eval(1)
  + Critique(4) + checkpoint_eval(1)
  + Extraction 重做(6) + checkpoint_eval(1)
  + Critique 重审(4) + checkpoint_eval(1)
  + Publish(6) + checkpoint_eval(1)
  = ~38 节点

设 recursion_limit = 50，留 ~30% 余量。
```

---

## 六、设计决策索引

| #   | 决策项           | 选择                                                              | 章节 |
| --- | ---------------- | ----------------------------------------------------------------- | ---- |
| 1   | State 关系模型   | 共享基座 + 私有扩展 + input/output schema                         | 一   |
| 2   | SharedState 字段 | 4 字段（messages, workspace_id, discipline, artifacts），永不扩充 | 1.2  |
| 3   | 路由机制         | 硬规则门禁 + LLM 结构化输出                                       | 2.1  |
| 4   | 规划模式         | Pre-plan + 检查点回评                                             | 2.4  |
| 5   | WF 内部路由      | 确定性条件边优先，语义判断用 LLM                                  | 3.1  |
| 6   | 循环退出         | 四重保障（计数器 + 条件边 + 时间/Token 预算 + recursion_limit）   | 3.2  |
| 7   | HITL 节点        | 独立确认节点，单一职责                                            | 3.3  |
| 8   | artifacts 结构   | 按 WF 命名空间隔离                                                | 4.2  |
| 9   | Critique 打回    | feedback 走 messages 注入，上游 WF 无感知                         | 4.3  |
| 10  | Checkpoint 范围  | 全量默认，每节点自动 checkpoint                                   | 5.1  |
| 11  | Thread 恢复      | MVP 只支持自动恢复最新 checkpoint                                 | 5.4  |
| 12  | Checkpoint 清理  | MVP 不做自动清理（YAGNI）                                         | 5.1  |
