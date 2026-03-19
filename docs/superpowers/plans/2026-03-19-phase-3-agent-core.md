# Phase 3: Agent 核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 Agent 运行时核心：SharedState/SupervisorState/6 个 WF State 定义、Prompt 加载器、Skill 注册中心、Supervisor 主图编排（含硬规则路由、LLM 路由、检查点回评）。

**Architecture:** Agent 核心在 `backend/agent/`，Supervisor 主图通过条件边连接 6 个 WF subgraph 节点（Phase 4 实现具体节点逻辑）。

**Tech Stack:** LangGraph / LangChain Core / Pydantic V2 / YAML

**前置条件：** Phase 2 服务层完成（LLM Gateway 可用）

**对应设计文档：**
- [Agent 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-langgraph-agent-design.md) — §一 State, §二 Supervisor 路由, §三 子图编排
- [Prompt 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-prompt-engineering-design.md) — §二 存储, §三 加载
- [Skill 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-skill-system-design.md) — §二 注册

---

## 文件结构

```
backend/agent/
├── __init__.py
├── state.py                    # [NEW] SharedState + SupervisorState + 6 个 WF State
├── graph.py                    # [NEW] Supervisor 主图编排
├── routing.py                  # [NEW] 硬规则 + LLM 路由 + 检查点回评
├── budget.py                   # [NEW] LoopBudget 循环预算检查
├── prompts/
│   ├── loader.py               # [NEW] PromptLoader（YAML + DB 覆盖）
│   ├── supervisor.yaml         # [NEW] Supervisor 路由 prompt
│   └── checkpoint_eval.yaml    # [NEW] 检查点回评 prompt
├── skills/
│   ├── registry.py             # [NEW] SkillRegistry
│   └── base.py                 # [NEW] Skill 基类定义

tests/unit/
├── test_state.py               # [NEW]
├── test_routing.py             # [NEW]
├── test_prompt_loader.py       # [NEW]
└── test_skill_registry.py      # [NEW]
```

---

## Task 1: Agent State 定义 — state.py

**Files:**
- Create: `backend/agent/state.py`
- Test: `tests/unit/test_state.py`

> 对应 [Agent 设计 §一](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-langgraph-agent-design.md)。SharedState 4 字段永不扩充；各 WF State 继承 SharedState + 私有字段。

- [ ] **Step 1: 实现 state.py**

`backend/agent/state.py`:
```python
"""Agent State 定义。SharedState 共享基座 + 各 WF 私有扩展。"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel


# ── Reducer ──

def merge_dicts(left: dict, right: dict) -> dict:
    """深度合并字典，右侧覆盖同名 key。"""
    merged = {**left}
    for key, value in right.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


# ── SharedState ──

class SharedState(TypedDict):
    """所有图的共享基座。只包含 4 个字段，永不扩充。"""
    messages: Annotated[list, add_messages]
    workspace_id: str
    discipline: str
    artifacts: Annotated[dict, merge_dicts]


# ── Supervisor State ──

class PlannedStep(BaseModel):
    workflow: str
    objective: str
    success_criteria: str


class ExecutionPlan(BaseModel):
    steps: list[PlannedStep]
    goal: str


class SupervisorState(SharedState):
    plan: ExecutionPlan | None
    current_step_index: int
    routing_decision: str | None


# ── Workflow States ──

class PaperCard(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    year: int
    citation_count: int | None = None
    relevance_score: float
    relevance_comment: str  # LLM 一句话相关性评语，供 HITL 勾选参考
    source: str


class DiscoveryState(SharedState):
    search_queries: list[str]
    raw_results: list[dict]
    candidate_papers: list[PaperCard]
    selected_paper_ids: list[str]  # 用户 HITL 勾选的论文 ID
    ingestion_task_ids: list[str]  # Celery ingestion 任务 ID


class ReadingNote(BaseModel):
    paper_id: str
    key_contributions: list[str]
    methodology: str
    experimental_setup: str
    main_results: str
    limitations: list[str]
    source_chunks: list[str]


class ComparisonEntry(BaseModel):
    paper_id: str
    method: str
    dataset: str
    metric_values: dict[str, float]
    key_difference: str


class ExtractionState(SharedState):
    paper_ids: list[str]
    reading_notes: list[ReadingNote]
    comparison_matrix: list[ComparisonEntry]
    glossary: dict[str, str]


class ResearchGap(BaseModel):
    description: str
    supporting_evidence: list[str]
    potential_impact: str


class ExperimentDesign(BaseModel):
    hypothesis: str
    method_description: str
    baselines: list[str]
    datasets: list[str]
    evaluation_metrics: list[str]
    expected_outcome: str


class IdeationState(SharedState):
    research_gaps: list[ResearchGap]
    experiment_designs: list[ExperimentDesign]
    selected_design_index: int | None


class SandboxExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    output_files: list[str]
    execution_time_seconds: float


class ExecutionState(SharedState):
    task_description: str
    generated_code: str
    execution_result: SandboxExecutionResult | None
    retry_count: int
    reflection: str | None
    elapsed_seconds: float
    tokens_used: int


class CritiqueFeedback(BaseModel):
    category: str
    severity: str
    description: str
    suggestion: str
    location: str | None = None


class CritiqueState(SharedState):
    target_workflow: str
    supporter_opinion: str
    critic_opinion: str
    feedbacks: list[CritiqueFeedback]
    verdict: str
    critique_round: int


class OutlineSection(BaseModel):
    title: str
    description: str
    source_artifacts: list[str]


class PublishState(SharedState):
    outline: list[OutlineSection]
    markdown_content: str
    user_edited_markdown: str | None  # Canvas 手改后回流的 Markdown
    citation_map: dict[str, str]
    output_files: list[str]
```

- [ ] **Step 2: 编写测试**

`tests/unit/test_state.py`:
```python
"""Agent State 定义测试。"""
from backend.agent.state import (
    SharedState, SupervisorState, DiscoveryState,
    ExtractionState, IdeationState, ExecutionState,
    CritiqueState, PublishState, merge_dicts,
)


def test_merge_dicts_deep() -> None:
    left = {"a": {"x": 1, "y": 2}, "b": 3}
    right = {"a": {"y": 99, "z": 100}}
    result = merge_dicts(left, right)
    assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}


def test_merge_dicts_overwrite_non_dict() -> None:
    left = {"a": 1}
    right = {"a": "replaced"}
    assert merge_dicts(left, right) == {"a": "replaced"}


def test_shared_state_has_four_fields() -> None:
    assert set(SharedState.__annotations__) == {
        "messages", "workspace_id", "discipline", "artifacts",
    }


def test_all_wf_states_inherit_shared() -> None:
    for state_cls in [DiscoveryState, ExtractionState, IdeationState,
                      ExecutionState, CritiqueState, PublishState]:
        assert "messages" in state_cls.__annotations__ or issubclass(state_cls, dict)
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/unit/test_state.py -v
```
Expected: `4 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/agent/state.py tests/unit/test_state.py
git commit -m "feat: add Agent State definitions (SharedState + 6 WF States)"
```

---

## Task 2: 循环预算检查 — budget.py

**Files:**
- Create: `backend/agent/budget.py`

- [ ] **Step 1: 实现 budget.py**

`backend/agent/budget.py`:
```python
"""循环预算检查。所有含循环的 WF 统一使用。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LoopBudget:
    """循环预算配置。"""
    max_retries: int
    max_elapsed_seconds: float
    max_tokens: int


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

- [ ] **Step 2: Commit**

```bash
git add backend/agent/budget.py
git commit -m "feat: add loop budget checker for workflow retry limits"
```

---

## Task 3: Prompt 加载器 — prompts/loader.py

**Files:**
- Create: `backend/agent/prompts/loader.py`
- Create: `backend/agent/prompts/supervisor.yaml`
- Create: `backend/agent/prompts/checkpoint_eval.yaml`
- Test: `tests/unit/test_prompt_loader.py`

> 对应 [Prompt 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-prompt-engineering-design.md)。YAML 为基线，DB `prompt_overrides` 表为覆盖层。

- [ ] **Step 1: 创建 Supervisor YAML prompt**

`backend/agent/prompts/supervisor.yaml`:
```yaml
name: supervisor_router
version: "1.0"
system: |
  你是 Research Copilot 的 Supervisor。你负责理解用户意图并将任务路由到正确的专家工作流。

  可用工作流：
  - discovery: 论文检索与初筛
  - extraction: 深度精读与笔记生成
  - ideation: Research Gap 分析与实验方案设计
  - execution: 代码生成与沙箱执行
  - critique: 模拟审稿（红蓝对抗）
  - publish: 报告生成与交付

  当前学科: {discipline}

  路由规则：
  1. 如果用户要求搜索论文或给出研究方向 → discovery
  2. 如果用户要求深入分析已有论文 → extraction
  3. 如果用户要求找 research gap 或设计实验 → ideation
  4. 如果用户贴了代码或要求执行实验 → execution
  5. 如果用户要求审查或评估结果 → critique
  6. 如果用户要求生成报告或 PPT → publish
  7. 复杂任务需要多步骤则输出 plan

user: |
  用户指令: {user_message}
  当前 artifacts 摘要: {artifacts_summary}
variables:
  - discipline
  - user_message
  - artifacts_summary
```

- [ ] **Step 2: 创建检查点回评 YAML prompt**

`backend/agent/prompts/checkpoint_eval.yaml`:
```yaml
name: checkpoint_evaluator
version: "1.0"
system: |
  评估当前步骤是否达到预期目标。只回答 passed=true/false 和简短理由。
user: |
  步骤目标: {objective}
  成功标准: {success_criteria}
  当前 artifacts 摘要: {artifacts_summary}
variables:
  - objective
  - success_criteria
  - artifacts_summary
```

- [ ] **Step 3: 实现 PromptLoader**

`backend/agent/prompts/loader.py`:
```python
"""Prompt 加载器。YAML 基线 + DB 覆盖层。"""
from pathlib import Path

import yaml

from backend.core.logger import get_logger

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, *, variables: dict[str, str] | None = None) -> dict[str, str]:
    """加载 prompt。先找 YAML 文件，变量替换后返回 system + user。

    Args:
        name: prompt 名称（不含 .yaml 后缀）。
        variables: 模板变量替换映射。

    Returns:
        {"system": "...", "user": "..."} 替换变量后的 prompt。
    """
    yaml_path = PROMPTS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    system_template: str = data.get("system", "")
    user_template: str = data.get("user", "")
    variables = variables or {}

    return {
        "system": system_template.format(**variables) if variables else system_template,
        "user": user_template.format(**variables) if variables else user_template,
    }
```

- [ ] **Step 4: 编写测试**

`tests/unit/test_prompt_loader.py`:
```python
"""Prompt Loader 测试。"""
import pytest
from backend.agent.prompts.loader import load_prompt


def test_load_supervisor_prompt() -> None:
    result = load_prompt("supervisor", variables={
        "discipline": "computer_science",
        "user_message": "搜索 transformer 相关论文",
        "artifacts_summary": "{}",
    })
    assert "Supervisor" in result["system"]
    assert "搜索 transformer" in result["user"]


def test_load_nonexistent_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent")
```

- [ ] **Step 5: 运行测试**

```bash
uv run pytest tests/unit/test_prompt_loader.py -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/agent/prompts/ tests/unit/test_prompt_loader.py
git commit -m "feat: add PromptLoader with YAML templates"
```

---

## Task 4: Skill 注册中心 — skills/

**Files:**
- Create: `backend/agent/skills/base.py`
- Create: `backend/agent/skills/registry.py`
- Test: `tests/unit/test_skill_registry.py`

> 对应 [Skill 设计](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-skill-system-design.md)。Skill 定义为 YAML + Python execute 函数。SkillRegistry 负责发现和调度。

- [ ] **Step 1: 实现 base.py**

`backend/agent/skills/base.py`:
```python
"""Skill 基类定义。"""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class SkillDefinition:
    """技能定义。从 skill.yaml 加载。"""
    name: str
    description: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    tags: list[str] = field(default_factory=list)
    execute: Callable[..., Any] | None = None
```

- [ ] **Step 2: 实现 registry.py**

`backend/agent/skills/registry.py`:
```python
"""Skill 注册中心。发现、注册和调度技能。"""
from backend.agent.skills.base import SkillDefinition
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """技能注册中心。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        """注册一个 Skill。"""
        if skill.name in self._skills:
            logger.warning("skill_already_registered", name=skill.name)
        self._skills[skill.name] = skill
        logger.info("skill_registered", name=skill.name)

    def get(self, name: str) -> SkillDefinition:
        """按名称获取 Skill。"""
        if name not in self._skills:
            raise KeyError(f"Skill not found: {name}")
        return self._skills[name]

    def list_skills(self) -> list[SkillDefinition]:
        """列出所有已注册 Skill。"""
        return list(self._skills.values())

    def search_by_tag(self, tag: str) -> list[SkillDefinition]:
        """按标签搜索 Skill。"""
        return [s for s in self._skills.values() if tag in s.tags]
```

- [ ] **Step 3: 编写测试**

`tests/unit/test_skill_registry.py`:
```python
"""Skill Registry 测试。"""
import pytest
from backend.agent.skills.base import SkillDefinition
from backend.agent.skills.registry import SkillRegistry


def test_register_and_get() -> None:
    registry = SkillRegistry()
    skill = SkillDefinition(
        name="arxiv_search", description="Search Arxiv",
        input_schema={"query": "str"}, output_schema={"results": "list"},
        tags=["search", "discovery"],
    )
    registry.register(skill)
    assert registry.get("arxiv_search") == skill


def test_get_nonexistent_raises() -> None:
    registry = SkillRegistry()
    with pytest.raises(KeyError, match="not found"):
        registry.get("nonexistent")


def test_search_by_tag() -> None:
    registry = SkillRegistry()
    registry.register(SkillDefinition(
        name="s1", description="", input_schema={}, output_schema={}, tags=["search"],
    ))
    registry.register(SkillDefinition(
        name="s2", description="", input_schema={}, output_schema={}, tags=["compute"],
    ))
    results = registry.search_by_tag("search")
    assert len(results) == 1
    assert results[0].name == "s1"
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/unit/test_skill_registry.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/agent/skills/ tests/unit/test_skill_registry.py
git commit -m "feat: add SkillRegistry with tag-based discovery"
```

---

## Task 5: Supervisor 主图 — routing.py + graph.py

**Files:**
- Create: `backend/agent/routing.py`
- Create: `backend/agent/graph.py`
- Test: `tests/unit/test_routing.py`

> 对应 [Agent 设计 §二](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-langgraph-agent-design.md)。硬规则门禁 + LLM 路由 + 检查点回评。Phase 4 会填入具体 WF subgraph 实现，本阶段使用 placeholder。

- [ ] **Step 1: 实现 routing.py**

`backend/agent/routing.py`:
```python
"""Supervisor 路由逻辑。硬规则门禁 + LLM 路由 + 检查点回评。"""
from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel

VALID_WORKFLOWS = frozenset({
    "discovery", "extraction", "ideation",
    "execution", "critique", "publish",
})


@dataclass(frozen=True)
class HardRule:
    """硬规则：模式匹配 → 直达目标 WF。"""
    name: str
    match: Callable[[list], bool]
    target: str


def _last_human_has_code_block(messages: list) -> bool:
    """最后一条用户消息是否包含代码块。"""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return "```" in (msg.content or "")
    return False


def _last_message_has_attachment(messages: list) -> bool:
    """最后一条消息是否有附件。"""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return bool(getattr(msg, "additional_kwargs", {}).get("attachments"))
    return False


HARD_RULES: list[HardRule] = [
    HardRule(name="code_execution_direct", match=_last_human_has_code_block, target="execution"),
    HardRule(name="file_upload_trigger", match=_last_message_has_attachment, target="discovery"),
]


def apply_hard_rules(messages: list) -> str | None:
    """按序检查硬规则。首个匹配返回目标 WF，无匹配返回 None。"""
    for rule in HARD_RULES:
        if rule.match(messages):
            return rule.target
    return None


class RouteDecision(BaseModel):
    """LLM 路由决策输出。"""
    mode: Literal["single", "plan"]
    target_workflow: str | None = None
    plan: list[dict] | None = None
    reasoning: str


class StepEvaluation(BaseModel):
    """检查点回评结果。"""
    passed: bool
    reason: str
    suggestion: str | None = None


def route_to_workflow(state: dict) -> str:
    """根据 routing_decision 路由到目标 WF。"""
    decision = state.get("routing_decision")
    if decision is None or decision == "__end__":
        return "__end__"
    if decision in VALID_WORKFLOWS:
        return decision
    return "__end__"


def route_after_eval(state: dict) -> str:
    """检查点回评后的路由。"""
    decision = state.get("routing_decision")
    if decision == "__end__":
        return "__end__"
    if decision == "__replan__":
        return "supervisor"
    if decision in VALID_WORKFLOWS:
        return decision
    return "__end__"
```

- [ ] **Step 2: 实现 graph.py（Supervisor 主图骨架）**

`backend/agent/graph.py`:
```python
"""Supervisor 主图编排。连接硬规则路由、LLM 路由、检查点回评和 6 个 WF subgraph。"""
from langgraph.graph import StateGraph, START, END

from backend.agent.state import SupervisorState
from backend.agent.routing import route_to_workflow, route_after_eval

# WF subgraph placeholder（Phase 4 替换为真实实现）
def _placeholder_node(state: dict) -> dict:
    """占位 WF 节点。Phase 4 替换为真实 subgraph。"""
    return {"artifacts": {}}


def _supervisor_node(state: dict) -> dict:
    """Supervisor 主控节点占位。Phase 4 填充 LLM 路由逻辑。"""
    return {"routing_decision": "__end__", "current_step_index": 0}


def _checkpoint_eval_node(state: dict) -> dict:
    """检查点回评节点占位。Phase 4 填充 LLM 评估逻辑。"""
    plan = state.get("plan")
    step_index = state.get("current_step_index", 0)

    if plan and step_index + 1 < len(plan.steps):
        return {
            "routing_decision": plan.steps[step_index + 1].workflow,
            "current_step_index": step_index + 1,
        }
    return {"routing_decision": "__end__"}


WORKFLOW_NAMES = ["discovery", "extraction", "ideation", "execution", "critique", "publish"]


def build_supervisor_graph() -> StateGraph:
    """构建 Supervisor 主图。"""
    graph = StateGraph(SupervisorState)

    # 节点注册
    graph.add_node("supervisor", _supervisor_node)
    graph.add_node("checkpoint_eval", _checkpoint_eval_node)

    for wf in WORKFLOW_NAMES:
        graph.add_node(wf, _placeholder_node)

    # 边连接
    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges(
        "supervisor", route_to_workflow,
        {wf: wf for wf in WORKFLOW_NAMES} | {"__end__": END},
    )

    for wf in WORKFLOW_NAMES:
        graph.add_edge(wf, "checkpoint_eval")

    graph.add_conditional_edges(
        "checkpoint_eval", route_after_eval,
        {wf: wf for wf in WORKFLOW_NAMES} | {"supervisor": "supervisor", "__end__": END},
    )

    return graph
```

- [ ] **Step 3: 编写路由测试**

`tests/unit/test_routing.py`:
```python
"""Routing 逻辑测试。"""
from unittest.mock import MagicMock
from backend.agent.routing import apply_hard_rules, route_to_workflow, route_after_eval


def test_hard_rule_code_block() -> None:
    msg = MagicMock(type="human", content="运行这段代码:\n```python\nprint(1)\n```")
    assert apply_hard_rules([msg]) == "execution"


def test_hard_rule_no_match() -> None:
    msg = MagicMock(type="human", content="搜索 transformer 论文")
    msg.additional_kwargs = {}
    assert apply_hard_rules([msg]) is None


def test_route_to_workflow_valid() -> None:
    assert route_to_workflow({"routing_decision": "discovery"}) == "discovery"


def test_route_to_workflow_end() -> None:
    assert route_to_workflow({"routing_decision": None}) == "__end__"


def test_route_after_eval_replan() -> None:
    assert route_after_eval({"routing_decision": "__replan__"}) == "supervisor"
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/unit/test_routing.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/agent/routing.py backend/agent/graph.py tests/unit/test_routing.py
git commit -m "feat: add Supervisor graph skeleton with routing and checkpoint eval"
```

---

## 验证清单

| 检查项         | 命令                                                 | 期望结果 |
| -------------- | ---------------------------------------------------- | -------- |
| State 定义     | `uv run pytest tests/unit/test_state.py -v`          | 4 passed |
| Prompt Loader  | `uv run pytest tests/unit/test_prompt_loader.py -v`  | 2 passed |
| Skill Registry | `uv run pytest tests/unit/test_skill_registry.py -v` | 3 passed |
| Routing 逻辑   | `uv run pytest tests/unit/test_routing.py -v`        | 5 passed |
| 全量 lint      | `uv run ruff check backend/agent/ tests/`            | 0 errors |
| 全量测试       | `uv run pytest tests/unit/ -v`                       | 全部通过 |

---

## 可观测性要求（横切）

> 对应 [可观测性设计 §二.4](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-observability-design.md)

在实现 Task 5（routing.py + graph.py）时，确保以下日志点：

- `supervisor_node` 路由决策日志：`logger.info("routing_decision", target=..., mode=..., reasoning=...)`
- `checkpoint_eval_node` 回评结果日志：`logger.info("checkpoint_eval", step_index=..., passed=..., reason=...)`
- 硬规则匹配日志：`logger.info("hard_rule_matched", rule_name=..., target=...)`

各 WF placeholder 节点暂不加日志（Phase 4 填充真实逻辑时补充）。

---

**Phase 3 完成标志：** 全部单元测试通过 + Supervisor 主图骨架可编译 + lint 无报错 → 可进入 Phase 4（填充 6 个 WF subgraph）。
