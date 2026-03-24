# Agent 优化实现计划 (v2)

> 修订日期：2026-03-21
> 关联 Spec：[agent-optimization-design.md](../specs/2026-03-21-agent-optimization-design.md) 、[prompt-engineering-design.md](../specs/2026-03-19-prompt-engineering-design.md)

---

## 〇、v1 修正说明

v1 计划存在 4 个架构性问题，此版本全部修正：

| #    | v1 问题                                                                                                                                         | v2 修正                                                                                                                                           |
| :--- | :---------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1    | 把「DSPy 接入」与「Prompt 体系重构」绑死。实际 `load_prompt()` 只是同步 YAML 读取函数，不存在 `PromptLoader` 类/DB 查询/`PromptTemplate` 抽象。 | **完全解耦**。DSPy 模块注册表独立于 `load_prompt()`，两条路径互不依赖。Prompt 体系的 DB 覆盖层重构推迟到独立 PR。                                 |
| 2    | 用 sentinel exception 在 `PromptLoader` 里跳转 DSPy 路径，把文本模板加载和可执行模块加载耦合在一起。                                            | **独立注册表** `ModuleRegistry`，只在显式改造的节点（`supervisor_node`、`filter_and_rank`）中直接调用，不侵入 `load_prompt()`。                   |
| 3    | 假设 `prompt_overrides` 已有 JSONB/唯一索引/查询逻辑。实际 ORM 只有 5 个 `Text`/`Boolean` 字段壳子，无运行时调用。                              | **不依赖 `prompt_overrides`**。DSPy 编译产物存为 JSON 文件，通过 `ModuleRegistry` 加载。`prompt_overrides` 的补全归入 Prompt 体系 Spec 独立推进。 |
| 4    | Discovery 训练数据从 LangGraph checkpoints 反挖，强依赖 checkpoint 内部存储结构。                                                               | **业务表采集**。在 `present_candidates` HITL 节点返回后，将 `(query, candidates, selected_ids)` 显式写入 `discovery_feedback` 业务表。            |

---

## 一、设计决策

### 1.1 DSPy 与现有系统的关系

```
现有系统 (不改动)                    新增 DSPy 层 (本计划范围)
─────────────────────                ─────────────────────────
load_prompt() → YAML                ModuleRegistry → compiled JSON
     ↓                                    ↓
llm.with_structured_output()         dspy.Module.forward()
     ↓                                    ↓
返回 Pydantic 对象                    返回 Pydantic 对象
```

**两条路径完全独立**。改造节点时，只是把 `load_prompt() + llm.invoke()` 替换为 `registry.get(name).forward()`。未改造的节点继续走 YAML 路径，零影响。

### 1.2 `ModuleRegistry` 设计

```python
from pathlib import Path
import dspy

COMPILED_DIR = Path(__file__).parent.parent / "compiled_prompts"

class ModuleRegistry:
    """DSPy 编译模块注册表。应用启动时扫描 compiled_prompts/ 目录，按名称注册。"""

    def __init__(self, compiled_dir: Path = COMPILED_DIR) -> None:
        self._modules: dict[str, dspy.Module] = {}
        self._compiled_dir = compiled_dir

    def register(self, name: str, module: dspy.Module) -> None:
        compiled_path = self._compiled_dir / f"{name}.json"
        if compiled_path.exists():
            module.load(str(compiled_path))
        self._modules[name] = module

    def get(self, name: str) -> dspy.Module | None:
        return self._modules.get(name)

    def has(self, name: str) -> bool:
        return name in self._modules
```

在节点中的使用方式：

```python
# supervisor_node 中
module = registry.get("supervisor_routing")
if module is not None:
    decision = module(discipline=..., chat_history=..., current_artifacts=...)
else:
    # 回退到现有 YAML + with_structured_output 路径
    decision = llm.with_structured_output(RouteDecision).invoke(...)
```

---

## 二、新增文件详表

### Phase 1 — DSPy 基础设施（与 Prompt 体系解耦）

#### [NEW] `backend/agent/dspy_modules/__init__.py`
导出 `ModuleRegistry` 单例和各 Module 类。

#### [NEW] `backend/agent/dspy_modules/registry.py`
`ModuleRegistry` 实现（见 1.2 节）。

#### [NEW] `backend/agent/dspy_modules/supervisor.py`
`SupervisorRoutingSignature` 和 `SupervisorRouterModule`（见 agent-optimization-design.md § 3.1）。

#### [NEW] `backend/agent/dspy_modules/discovery.py`
`PaperRankingSignature` 和 `FilterRankModule`（见 agent-optimization-design.md § 4.1）。

#### [NEW] `backend/agent/compiled_prompts/.gitkeep`
空目录占位。编译产物 `*.json` 加入 `.gitignore`。

#### [MODIFY] `pyproject.toml`
添加 `dspy` 依赖（`[project.optional-dependencies]` 下的 `optimization` 组）。

---

### Phase 2 — Supervisor 路由优化

#### [NEW] `backend/agent/optimizers/datasets/supervisor_gen.py`

用强模型合成 300 条路由标注样本。分布先验：

| 类别      | 比例 | 目标         |
| :-------- | :--- | :----------- |
| 单步搜索  | 25%  | `discovery`  |
| 单步精读  | 25%  | `extraction` |
| 单步代码  | 20%  | `execution`  |
| 多步计划  | 20%  | `plan`       |
| 聊天/澄清 | 10%  | `chat`       |

#### [NEW] `backend/agent/optimizers/metrics/supervisor_metric.py`

加权路由评分函数（见 agent-optimization-design.md § 3.3）。

#### [NEW] `backend/agent/optimizers/run_supervisor.py`

MIPROv2 编译脚本，产物写入 `compiled_prompts/supervisor_routing.json`。

#### [MODIFY] `backend/agent/graph.py`

修改 `supervisor_node`：启动时通过 `ModuleRegistry` 尝试加载编译模块，`get()` 返回 `None` 时回退到现有 YAML 路径。

---

### Phase 3 — Discovery 排序优化

#### [NEW] `backend/models/discovery_feedback.py`

**新增业务表**，显式记录每次 HITL 选择行为：

```python
class DiscoveryFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Discovery WF 的 HITL 隐式反馈记录。"""
    __tablename__ = "discovery_feedback"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    discipline: Mapped[str] = mapped_column(Text, nullable=False)
    candidates_json: Mapped[str] = mapped_column(Text, nullable=False)
    selected_paper_ids: Mapped[str] = mapped_column(Text, nullable=False)
```

**数据采集点**：在 `present_candidates` 节点的 `interrupt` 返回后、`return` 之前，调用 `save_discovery_feedback()` 写入该表。不依赖 checkpoint 内部结构。

#### [MODIFY] `backend/agent/workflows/discovery/nodes.py`

在 `present_candidates` 节点追加 feedback 持久化：

```python
def present_candidates(state: DiscoveryState) -> dict:
    candidates = state.get("candidate_papers", [])
    response = interrupt({...})
    selected_ids = response.get("selected_ids", [])

    # 新增：写入业务表供 DSPy 训练用
    save_discovery_feedback(
        workspace_id=state.get("workspace_id", ""),
        thread_id=state.get("thread_id", ""),
        user_query=get_last_user_message(state["messages"]),
        discipline=state.get("discipline", ""),
        candidates=candidates,
        selected_ids=selected_ids,
    )

    return {"selected_paper_ids": selected_ids}
```

#### [NEW] `backend/agent/optimizers/datasets/discovery_extract.py`

从 `discovery_feedback` 业务表（非 checkpoint）中读取并构建 `dspy.Example` 数据集。

#### [NEW] `backend/agent/optimizers/metrics/discovery_metric.py`

- `discovery_relevance_metric()` — DSPy per-sample Margin Ranking 评分。
- `compute_ndcg_at_k()` — 离线批量 nDCG@K 报告（脱离 DSPy 框架）。

#### [NEW] `backend/agent/optimizers/run_discovery.py`

BootstrapFewShotWithRandomSearch 编译脚本。

#### [MODIFY] `backend/agent/workflows/discovery/nodes.py`

修改 `filter_and_rank`：通过 `ModuleRegistry` 加载编译模块，回退到现有 YAML 路径。

---

## 三、明确不在本计划范围

以下事项与 DSPy 优化无依赖关系，各自独立推进：

| 事项                                                      | 归属 Spec                          | 状态                           |
| :-------------------------------------------------------- | :--------------------------------- | :----------------------------- |
| `PromptLoader` 类抽象（DB 覆盖层、`PromptTemplate` 对象） | prompt-engineering-design.md § 2   | 待独立 PR                      |
| `prompt_overrides` 表 JSONB 迁移、唯一索引、查询逻辑      | prompt-engineering-design.md § 2.2 | 待独立 PR                      |
| GEPA 集成架构                                             | prompt-engineering-design.md § 5   | 待 DSPy MVP 验证后再评估       |
| 三层 Prompt 优先级统一 (DSPy > DB > YAML)                 | 两份 Spec 联动                     | 待 PromptLoader 重构完成后再做 |

---

## 四、统一 Evaluator 覆盖表

| 优先级 | 节点                        | Metric                  | 数据来源                    | 阶段           |
| :----- | :-------------------------- | :---------------------- | :-------------------------- | :------------- |
| **P0** | `supervisor_node`           | 路由分类准确率（加权）  | 合成数据 300 条             | Phase 2        |
| **P0** | `filter_and_rank`           | Margin Ranking + nDCG@5 | `discovery_feedback` 业务表 | Phase 3        |
| P1     | `critique/judge`            | 裁决准确率              | 人工埋点好/坏产出物         | 后续           |
| P1     | `execution/generate_code`   | 执行成功率              | 历史任务及预期结果          | 后续           |
| P2     | `discovery/expand_query`    | 召回率                  | 历史 (query, papers) 对     | 后续 Multi-Hop |
| P2     | `extraction/generate_notes` | 覆盖率 + 准确性         | 人工精读对照                | 后续           |

---

## 五、验证计划

### 5.1 单元测试

```bash
uv run pytest tests/unit/optimizers/test_supervisor_metric.py -v
uv run pytest tests/unit/optimizers/test_discovery_metric.py -v
uv run pytest tests/unit/optimizers/test_module_registry.py -v
```

**`test_module_registry.py` 核心用例**：

| Case                                          | 期望             |
| :-------------------------------------------- | :--------------- |
| `compiled_prompts/` 为空，`get()` 返回 `None` | 回退到 YAML 路径 |
| 放入合法 JSON，`get()` 返回已加载的 Module    | DSPy 路径生效    |
| JSON 格式损坏，`register()` 抛出明确异常      | 不静默失败       |

### 5.2 集成测试

```bash
# 生成合成数据
uv run python -m backend.agent.optimizers.datasets.supervisor_gen --output data/supervisor_train.jsonl

# Baseline 评估
uv run python -m backend.agent.optimizers.run_supervisor --eval-only

# MIPROv2 优化
uv run python -m backend.agent.optimizers.run_supervisor

# 期望: 优化后 Accuracy >= Baseline
```

### 5.3 手动验证

1. **回退**：删除 `compiled_prompts/supervisor_routing.json`，重启服务，正常路由。日志显示 `"dspy_module_not_found, fallback=yaml"`。
2. **Discovery 反馈采集**：执行一次 Discovery 流程，在 HITL 勾选后，查询 `discovery_feedback` 表确认记录已写入。
