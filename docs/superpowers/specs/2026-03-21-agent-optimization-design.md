# Agent 优化与衡量规范 (Agent Optimization & Evaluation Spec)

> 生效日期：2026-03-21
> 目标：基于 DSPy 为 Research Copilot 建立一套无需重构核心架构的量化评估与 Prompt 自动优化体系。
> 阶段：Phase 1 MVP (切入点: Supervisor 路由决策 + Discovery 寻源初筛)

---

## 一、引言与核心设计准则

随着 Research Copilot 的功能逐步完善，现有的「人工调试 Prompt」模式已遇到瓶颈：修改一处 Prompt 可能导致意外的回归退化（Regression），且缺乏系统性的指标来衡量 Agent 的表现到底是提升了还是下降了。

为了实现**系统级的自我进化**，引入 [DSPy](https://dspy.ai/) 框架。DSPy 的核心理念是**「Programming, not Prompting」**——通过定义清晰的任务签名（Signature）、模块（Module）和度量指标（Metric），让优化器（Optimizer）自动寻找最优的 Prompt 和少样本（Few-shot）示例。

### 1.1 设计决策

| 决策维度       | 方案选择                   | 设计考量                                                                                                                                                      |
| :------------- | :------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **基础架构**   | **保留 LangGraph 编排**    | LangGraph 提供了完美的图流转、并发控制、State 管理和 HITL 机制，这些是 DSPy 自身的 `dspy.ReAct` 等粗粒度抽象所不具备的。                                      |
| **集成深度**   | **局部节点 Drop-in 替换**  | 仅将计算图中的 `llm.with_structured_output()` 替换为编译好的 `dspy.Module`。系统其余部分对 DSPy 无感知。                                                      |
| **数据集策略** | **混合渐进式 (Hybrid)**    | 冷启动：利用强模型（GPT-4o/Claude-3.5-Sonnet）批量生成合成数据（Synthetic Data）。<br>成熟期：消费生产环境的历史执行日志以及用户的隐式反馈（HITL 勾选行为）。 |
| **指标原则**   | **可计算的确定性指标优先** | 优先优化存在客观 Ground Truth 或可通过算法确定得分的任务（如分类准确率、排序 nDCG），后逐步推向更模糊的生成任务。                                             |

---

## 二、DSPy 集成架构层设计

### 2.1 运行时组件交互图

整个系统的运行态与优化态将发生结构性分离。线上系统执行（Inference）与离线优化（Optimization）分为两套不同的生命周期。

```text
       [ 离线优化流水线 (Offline Optimization) ]

 ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
 │ Benchmark 数据 │ ──► │ DSPy Optimizer│ ──► │  Compiled    │
 │ (合成 / 真实)  │     │ (MIPROv2 等)   │     │ DSPy Module  │
 └──────────────┘     └──────┬────────┘     └──────┬───────┘
                             │                     │
                             │ (Evaluate)          │ (Save/Load)
                             ▼                     ▼
 ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
 │  Metric 函数  │ ◄── │ LLM Backend   │     │ JSON / Pickle│
 └──────────────┘     └───────────────┘     └──────┬───────┘
                                                   │
===================================================│=================
                                                   │
       [ 线上运行时 (Online Inference) ]           │ load
                                                   ▼
 ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
 │ LangGraph WF │ ──► │ Node Function │ ──► │ DSPy Module  │
 │ (State 流转)  │     │ (注入 State)   │     │ (前向传播)    │
 └──────────────┘     └───────────────┘     └──────┬───────┘
                                                   │
                                                   ▼
                                            ┌──────────────┐
                                            │ LLM Backend  │
                                            └──────────────┘
```

### 2.2 目录结构扩展

在现有的 `backend/agent/` 目录中增加 `dspy_modules/` 和 `optimizers/` 两层抽象。

```text
backend/agent/
├── dspy_modules/          # 存放定义了输入输出接口的 DSPy Signature 和 Module
│   ├── __init__.py
│   ├── supervisor.py      # RouteDecisionModule
│   └── discovery.py       # FilterRankModule, ExpandQueryModule
├── optimizers/            # 离线优化脚本和数据集构建逻辑
│   ├── __init__.py
│   ├── datasets/          # 存放本地训练集/验证集加载逻辑
│   ├── metrics/           # 量化评估函数 (Accuracy, nDCG 等)
│   ├── run_supervisor.py  # 触发 Supervisor 优化的脚本
│   └── run_discovery.py   # 触发 Discovery 优化的脚本
└── compiled_prompts/      # 存放 DSPy 编译后的 JSON 文件（含 optimized prompts & few-shots）
```

---

## 三、MVP 模块 1：Supervisor 路由精准度优化

**痛点背景**：Supervisor 是请求的入口，如果它判断错了用户的意图（比如将需要深读的 Extraction 请求路由到了需要新建搜索的 Discovery，或者在该返回单步操作时返回了复杂的多步 plan），将带来巨大的资源浪费和时间延迟。这是一次典型的高难度**分类与规划问题**。

### 3.1 Signature 与 Module 定义

在 `dspy_modules/supervisor.py` 中定义抽象：

```python
import dspy
from pydantic import BaseModel
from typing import Literal

# 借用现有的 State Pydantic 定义
from backend.agent.routing import RouteDecision

class SupervisorRoutingSignature(dspy.Signature):
    """
    作为研究助手的核心路由，分析用户的请求，决定将其派发给哪个具体的 Workflow，
    或者为其制定一个多步工作流计划。
    """

    discipline = dspy.InputField(desc="用户的学科背景，如 'computer_science'")
    chat_history = dspy.InputField(desc="最近的对话上下文")
    current_artifacts = dspy.InputField(desc="当前已生成的研究产出物摘要")

    # DSPy 原生支持 Pydantic Output！自动注入格式化 Prompt 机制。
    routing_decision: RouteDecision = dspy.OutputField(
        desc="包含 mode (single/plan/chat), target_workflow, plan, reasoning 的结构化输出"
    )

class SupervisorRouterModule(dspy.Module):
    def __init__(self):
        super().__init__()
        # 考虑到路由需要思考其判断逻辑，强制使用 ChainOfThought
        self.prog = dspy.ChainOfThought(SupervisorRoutingSignature)

    def forward(self, discipline: str, chat_history: str, current_artifacts: str) -> RouteDecision:
        result = self.prog(
            discipline=discipline,
            chat_history=chat_history,
            current_artifacts=current_artifacts
        )
        return result.routing_decision
```

### 3.2 冷启动合成数据集 (Synthetic Dataset)

由于系统刚上线，没有足够的真实历史作为 Benchmark，我们使用“模型蒸馏”思路，利用更强大的模型体系（如 GPT-4o 或 Claude 3.5 Sonnet）根据特定规则批量生成高质量样本。

**合成流水线架构：**

1. 设定业务用例分布先验（例如：50% 直达查询，30% 多步写作，20% 代码计算）。
2. 让强模型扮演“各类不同专业背景、不同挑剔程度的 User”，随机生成 300 条请求场景。
3. 强模型扮演“完美的人类架构师”，为每一条请求场景直接填写符合 Ground Truth 的 `RouteDecision` JSON。
4. 人工进行 10% 的抽样检查，剔除荒谬数据。

**数据集存储格式 (Example Format):**
构建的 DSPy Example 应映射 Signature 的 Input/Output。

```python
dspy.Example(
    discipline="biology",
    chat_history="Human: 帮我查一下这篇 PMID: 3123456 的论文，提取里面的核心蛋白通路对比一下。",
    current_artifacts="[]",
    routing_decision=RouteDecision(
        mode="single",
        target_workflow="extraction",
        reasoning="用户已经提供了明确的文章 ID，不需要进行全面的文献搜索(Discovery)，可直接进入精读与结构化抽取阶段(Extraction)。",
        plan=None
    )
).with_inputs("discipline", "chat_history", "current_artifacts")
```

### 3.3 评估指标定义 (Metrics)

评估函数不仅需要返回 boolean 值，在微调框架中，最好返回浮点数（0.0 ~ 1.0），包含软匹配惩罚项。

```python
def supervisor_routing_metric(example: dspy.Example, pred: dspy.Example, trace=None) -> float:
    """计算 Supervisor 路由的精准度得分"""
    score = 0.0
    expected: RouteDecision = example.routing_decision
    predicted: RouteDecision = pred.routing_decision

    # 1. Mode 匹配 (权重 0.4)
    if expected.mode == predicted.mode:
        score += 0.4
    else:
        return 0.0  # 模式错了直接 0 分

    # 2. Workflow 目标匹配 (单路径模式下权重 0.6)
    if expected.mode == "single":
        if expected.target_workflow == predicted.target_workflow:
            score += 0.6

    # 3. 计划路径合理性 (Plan 模式下权重 0.6)
    elif expected.mode == "plan":
        # 简单比对: 第一步的 workflow 是否正确
        if expected.plan and predicted.plan and expected.plan.steps and predicted.plan.steps:
            if expected.plan.steps[0].workflow == predicted.plan.steps[0].workflow:
                score += 0.3
            # 子步骤数量是否接近
            if abs(len(expected.plan.steps) - len(predicted.plan.steps)) <= 1:
                score += 0.3

    return score
```

### 3.4 优化器执行

在 `optimizers/run_supervisor.py` 中，使用 `MIPROv2` (Multi-prompt Instruction PRoposal Optimizer) 进行编译：

```python
from dspy.teleprompt import MIPROv2

teleprompter = MIPROv2(
    metric=supervisor_routing_metric,
    auto="light",       # 使用轻量级自动超参
    num_threads=8       # 并发运行加速
)

compiled_router = teleprompter.compile(
    SupervisorRouterModule(),
    trainset=trainset,
    valset=valset
)

compiled_router.save("compiled_prompts/supervisor_routing.json")
```

---

## 四、MVP 模块 2：Discovery 寻源召回率与排序优化

**痛点背景**：在 `filter_and_rank` 节点，当前实现是让 LLM 并发去读每一篇 Paper 的 Title 和 Abstract，然后输出一个粗糙的 `relevance_score`。
由于缺乏参照物，直接打分主观性极高。我们需要通过真实的用户选择（Human-in-the-Loop，用户勾选了哪些作为阅读对象），不断优化打分依据。

### 4.1 Signature 与 Module 定义

```python
class RelevanceCard(BaseModel):
    relevance_score: float
    relevance_comment: str

class PaperRankingSignature(dspy.Signature):
    """
    评估单篇学术论文与用户的初始研究查询的匹配程度并打分(0.0 到 1.0)。
    你需要给出一个精炼的相关性评价，指出它在哪个维度上契合查询。
    """
    discipline = dspy.InputField()
    user_search_intent = dspy.InputField(desc="用户原始的搜索表达及上下文")
    paper_title = dspy.InputField()
    paper_abstract = dspy.InputField()

    evaluation: RelevanceCard = dspy.OutputField()

class FilterRankModule(dspy.Module):
    def __init__(self):
        super().__init__()
        # 此处使用简单的 Predict，因为要求延迟低、高并发处理几十篇候选论文
        self.prog = dspy.Predict(PaperRankingSignature)

    def forward(self, discipline, user_search_intent, paper_title, paper_abstract):
        return self.prog(
            discipline=discipline,
            user_search_intent=user_search_intent,
            paper_title=paper_title,
            paper_abstract=paper_abstract
        )
```

### 4.2 热数据回流构建的数据集 (HITL Implicit Feedback)

这是引入 Agent 数据飞轮的最重要环节。

*数据收集点*：`discovery/nodes.py` 的 `present_candidates` 节点通过 `interrupt` 发送候选列表，拦截器返回了 `{"selected_paper_ids": []}`。

*数据提取*：
每当一个 Thread 完成 Discovery 工作流并结束这部分状态，提取状态集：
- 被用户最终选中的 Paper 记为正样本 (`label=1`)。
- 当页未被选中但提供给了用户的 Paper 记为负样本 (`label=0`)。

*聚合为 Rank 样本组*：
这不是典型的逐条分类衡量，而是列表排序衡量（Learning to Rank）。为了迎合 DSPy，我们需要将评价转化到单条记录上，但计算指标时基于 Group。

### 4.3 排序度量指标 (nDCG / Precision@K)

评估单个 Module 其实只是输出一个 RelevanceScore，实际的 Metric 需要在一个 List 的维度进行评估。DSPy 允许你将自定义的数据集切块计算。
为了便于在 DSPy 的单例示例层执行，我们将 Metric 转换为：**Margin Ranking Loss 的得分版**。

```python
def discovery_relevance_metric(example: dspy.Example, pred: dspy.Example, trace=None) -> float:
    """
    基于用户隐式反馈的评分。
    example.is_selected (bool): This paper was actually selected by human.
    """
    score: float = pred.evaluation.relevance_score
    is_selected: bool = example.is_selected

    if is_selected:
        # 选中的文章，LLM 评分越接近 1 则得分越高
        return max(0.0, score)
    else:
        # 未选中的文章，LLM 评分越低(越接近 0)则得分越高，如果强行打高分则倒扣
        return max(0.0, 1.0 - score)
```

更全局的评测（脱离单例 DSPy Compile 过程的报告）：我们将基于一组预测值对原始表列重排，计算 `nDCG@5`：
- 对于某次 user query，用户选了论文 A, C。
- LLM 对这 10 篇打分，如果它将 A, C 排在 Top 2，那么 nDCG 为 1.0。
- 这个单独作为一个可视化基准看板存在于可观测层。

### 4.4 优化策略
针对 `FilterRankModule` 运行 `BootstrapFewShotWithRandomSearch`（比 MIPRO 便宜稳妥），通过从历史选定的（Query - True Paper）组合中提取完美的 `relevance_comment`，自动构建 3-shot prompt，从而大幅提高其余 Paper 进行推断时的精度下限。

---

## 五、运行态无缝集成机制 (LangGraph 适配)

要在现有的 `node.py` 中使用编译好的模块，只需稍微改动初始化与调用过程。

**示例：在 `discovery/nodes.py` 中对接**

```python
import dspy
from backend.agent.dspy_modules.discovery import FilterRankModule

# 全局初始化，在应用启动时加载一次
# （需要前置进行 dspy.configure(lm=...) 保证 LM Client 注入）
try:
    optimized_filter_module = FilterRankModule()
    optimized_filter_module.load("backend/agent/compiled_prompts/filter_rank.json")
except Exception as e:
    logger.warning("未能加载 DSPy 编译模块，回退到 baseline", error=str(e))
    # 无需回退代码，DSPy module 若无 compile 文件，则使用纯 Prompt 的 zero-shot baseline 继续前向。

async def filter_and_rank(state: DiscoveryState, *, llm: BaseChatModel) -> dict:
    ...
    # 并发 LLM 评估相关性
    sem = asyncio.Semaphore(10)

    async def _evaluate_paper(paper: dict) -> PaperCard | None:
        async with sem:
            try:
                # 显式使用 DSPy Async 推理 (假设我们配置了 Async LM)
                result = await asyncio.to_thread(
                    optimized_filter_module,
                    discipline=discipline,
                    user_search_intent=state.get("messages", [])[-1].content,
                    paper_title=paper.get("title", ""),
                    paper_abstract=paper.get("abstract", "")
                )

                return PaperCard(
                    arxiv_id=paper.get("arxiv_id", ""),
                    # ... 填充
                    relevance_score=result.evaluation.relevance_score,
                    relevance_comment=result.evaluation.relevance_comment
                )
            except Exception as e:
                logger.warning("filter_rank_skip_paper", arxiv_id=paper.get("arxiv_id"))
                return None
    ...
```

---

## 六、长期演进路线图 (Roadmap)

### Phase 1: MVP (当前)
1. 建设 DSPy 基础目录和 `teleprompt` 脚手架。
2. 针对 **Supervisor (Router)** 用合成数据验证优化流程跑通，建立 Baseline 准确率和微调后准确率看板。
3. 针对 **Discovery (Filter & Rank)** 接入离线历史日志提取，并跑出 Baseline nDCG。

### Phase 2: 内容生成的质量优化 (Extraction & Critique)
1. **Extraction (阅读笔记与矩阵抽取)**：引入专家人工标注 Ground Truth（人工先完整精读一批论文，抽取完美矩阵）。使用 DSPy 优化 LLM 在抽取遗漏率、幻觉率。
2. **Critique (红蓝对抗评判精度)**：用确定的“好文章”与埋入了错误/逻辑断层的“脏文章”测试 Critic 和 Judge 的反应。Metric 是能否准确抓出埋点 Bug 并抛出 `verdict="revise"`。

### Phase 3: 多阶段联合微调 (Multi-Stage Pipeline Optimization)
突破单个孤立节点的提升（有时候上游节点虽然准确率提高，但其生成的中间态 token 反而导致了下游命中率下降）。
利用 [DSPy 的 Multi-Hop 能力](https://dspy.ai/tutorials/multi-hop/)：
联合优化 `Discovery.expand_query` -> `Discovery.filter_and_rank`，允许全局损失直接反馈给查询扩展器，它会自动学会应该扩展哪些“神仙长尾词”最能讨好后续的过滤器。

---

> _"If you aren't rigorously measuring your AI system, you aren't doing AI engineering. You're just vibing."_
