# Phase 4: Agent Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 实现 6 个专家工作流（Discovery → Extraction → Ideation → Execution → Critique → Publish），替换 Phase 3 中的 placeholder 节点。

**Architecture:** 每个 WF 在 `backend/agent/workflows/{name}/` 下独立实现（注意：Python 不支持数字开头的包名，因此不用 `{N}_` 前缀），包含 nodes.py（节点函数）、graph.py（subgraph 编排）。State 集中在顶层 `backend/agent/state.py`。

**前置条件：** Phase 3 Agent Core 完成

**对应设计文档：**
- [Agent 设计 §三](file:///home/wenmou/Projects/ResearchCopilot/backend/agent/budget.py)   | ✅ 完整 |
| Prompt Loader + 2 份 YAML               | `prompts/loader.py`, `supervisor.yaml`, `checkpoint_eval.yaml`                      | ✅ 基础 |
| Skill Registry + Base                   | `skills/registry.py`, `skills/base.py`                                              | ✅ 基础 |
| 4 个服务层模块                          | `llm_gateway`, `sandbox_manager`, `parser_engine`, `rag_engine`                     | ✅ 完整 |

## 设计决策

### 1. Prompt 文件粒度
每个 WF 一个 `prompts/{wf_name}/prompts.yaml`，按节点名分 key。loader 从对应目录加载。

```
prompts/
├── supervisor.yaml
├── checkpoint_eval.yaml
├── discovery/
│   └── prompts.yaml     # keys: expand_query, filter_and_rank, relevance_comment
├── extraction/
│   └── prompts.yaml     # keys: generate_notes, cross_compare, build_glossary
├── ideation/
│   └── prompts.yaml     # keys: analyze_gaps, generate_designs, select_design
├── execution/
│   └── prompts.yaml     # keys: generate_code, reflect_and_retry
├── critique/
│   └── prompts.yaml     # keys: supporter_review, critic_review, judge_verdict
└── publish/
    └── prompts.yaml     # keys: assemble_outline, generate_markdown
```

### 2. WF 目录结构
State 集中在顶层 `backend/agent/state.py`，WF 目录只含 `nodes.py` + `graph.py` + `__init__.py`。避免 State 继承关系的循环导入。

### 3. Discovery 外部 API
实现真实 API 调用（Arxiv/Semantic Scholar），通过依赖注入传入 client。单元测试全部 mock，真实 API 在 Phase 8 E2E 测试覆盖。

### 4. Critique 并行
先按 spec 用 `Send()` 实现并行。如果与 subgraph `input/output=SharedState` 不兼容，降级为顺序执行（逻辑一致，仅性能差异）。

---

## Task 1: Discovery WF — 寻源初筛

### 文件产出

| 文件                                            | 说明                         |
| ----------------------------------------------- | ---------------------------- |
| `backend/agent/workflows/discovery/__init__.py` | 导出 `build_discovery_graph` |
| `backend/agent/workflows/discovery/nodes.py`    | 6 个节点函数                 |
| `backend/agent/workflows/discovery/graph.py`    | subgraph 编排                |
| `backend/agent/prompts/discovery/prompts.yaml`  | 3 个 prompt                  |
| `tests/unit/test_wf_discovery.py`               | 单元测试                     |

### 节点设计

```
START → expand_query → search_apis → filter_and_rank → present_candidates(HITL) → trigger_ingestion → write_artifacts → END
```

| 节点                 | 输入 State 字段                      | 输出 State 字段                     | LLM 调用                   | 外部依赖                             |
| -------------------- | ------------------------------------ | ----------------------------------- | -------------------------- | ------------------------------------ |
| `expand_query`       | `messages[-1].content`, `discipline` | `search_queries: list[str]`         | ✅ 扩展查询词               | —                                    |
| `search_apis`        | `search_queries`                     | `raw_results: list[dict]`           | ❌                          | Arxiv API, Semantic Scholar API      |
| `filter_and_rank`    | `raw_results`                        | `candidate_papers: list[PaperCard]` | ✅ 生成 `relevance_comment` | —                                    |
| `present_candidates` | `candidate_papers`                   | `selected_paper_ids: list[str]`     | ❌                          | `interrupt()` HITL                   |
| `trigger_ingestion`  | `selected_paper_ids`                 | `ingestion_task_ids: list[str]`     | ❌                          | BFF document service（Phase 4 mock） |
| `write_artifacts`    | 全部私有字段                         | `artifacts["discovery"]`            | ❌                          | —                                    |

### 关键实现细节

- **expand_query**: LLM `with_structured_output` 输出 `list[str]`，将用户自然语言扩展为 3~5 个学术搜索查询
- **search_apis**: 调用外部 API，Phase 4 中通过参数注入 API client（便于 mock）
- **filter_and_rank**: 去重（arxiv_id）→ relevance_score 多维打分 → LLM 为 top-N 生成 `relevance_comment`
- **present_candidates**: `interrupt({"action": "select_papers", "candidates": [...]})`，用户 resume 时传回 `{"selected_ids": [...]}`
- **trigger_ingestion**: Phase 4 返回 mock task_id 列表；Phase 6 集成后调用真实 BFF
- **write_artifacts**: 写入 `artifacts["discovery"]`（命名空间约定见 spec §4.2）

### 测试要点

- mock LLM → 验证 `expand_query` 输出 `search_queries` 格式
- mock API → 验证 `filter_and_rank` 去重和排序
- mock `interrupt()` → 验证 HITL resume 路径
- 验证 `write_artifacts` 输出的 artifacts 结构符合命名空间约定

---

## Task 2: Extraction WF — 深度精读

### 文件产出

| 文件                                             | 说明                          |
| ------------------------------------------------ | ----------------------------- |
| `backend/agent/workflows/extraction/__init__.py` | 导出 `build_extraction_graph` |
| `backend/agent/workflows/extraction/nodes.py`    | 7 个节点函数                  |
| `backend/agent/workflows/extraction/graph.py`    | subgraph 编排                 |
| `backend/agent/prompts/extraction/prompts.yaml`  | 3 个 prompt                   |
| `tests/unit/test_wf_extraction.py`               | 单元测试                      |

### 节点设计

```
START → wait_rag_ready → check_existing_notes → retrieve_chunks → generate_notes → cross_compare → build_glossary → write_artifacts → END
```

| 节点                   | 输入                                           | 输出                                       | LLM          | 外部依赖                |
| ---------------------- | ---------------------------------------------- | ------------------------------------------ | ------------ | ----------------------- |
| `wait_rag_ready`       | `artifacts["discovery"]["selected_paper_ids"]` | （通过/抛异常）                            | ❌            | 轮询文档 `parse_status` |
| `check_existing_notes` | `artifacts["extraction"]`（如有）              | 过滤出需处理的 `paper_ids`                 | ❌            | —                       |
| `retrieve_chunks`      | `paper_ids`                                    | 每篇论文的 RAG chunks                      | ❌            | `rag_engine.retrieve()` |
| `generate_notes`       | chunks + `paper_ids`                           | `reading_notes: list[ReadingNote]`         | ✅ 逐篇生成   | —                       |
| `cross_compare`        | `reading_notes`                                | `comparison_matrix: list[ComparisonEntry]` | ✅ 跨文档对比 | —                       |
| `build_glossary`       | `reading_notes`                                | `glossary: dict[str, str]`                 | ✅ 术语提取   | —                       |
| `write_artifacts`      | 全部私有字段                                   | `artifacts["extraction"]`                  | ❌            | —                       |

### 关键实现细节

- **wait_rag_ready**: 轮询 document `parse_status`，超时（配置秒数）抛 `TimeoutError`。Phase 4 mock 为直接通过
- **check_existing_notes**: 增量分析核心——从 `state["reading_notes"]` 读取已有笔记，跳过已处理过的 paper_id
- **retrieve_chunks**: 调用 `rag_engine.retrieve()`，按 document_id 过滤，Phase 4 mock
- **generate_notes**: 逐篇论文调用 LLM，输出 `ReadingNote` 结构化对象
- **cross_compare**: 将所有 `reading_notes` 合并输入 LLM，输出 `ComparisonEntry` 列表
- **build_glossary**: 从全部笔记中提取专业术语，输出 `{term: definition}` 字典

### 测试要点

- mock RAG 返回 → 验证 `generate_notes` 生成 `ReadingNote` 结构
- 验证增量检查逻辑（已有笔记的论文被跳过）
- 验证 `cross_compare` 能处理 1 篇和多篇论文两种场景

---

## Task 3: Ideation WF — 实验推演

### 文件产出

| 文件                                           | 说明                        |
| ---------------------------------------------- | --------------------------- |
| `backend/agent/workflows/ideation/__init__.py` | 导出 `build_ideation_graph` |
| `backend/agent/workflows/ideation/nodes.py`    | 4 个节点函数                |
| `backend/agent/workflows/ideation/graph.py`    | subgraph 编排               |
| `backend/agent/prompts/ideation/prompts.yaml`  | 3 个 prompt                 |
| `tests/unit/test_wf_ideation.py`               | 单元测试                    |

### 节点设计

```
START → analyze_gaps → generate_designs → select_design → write_artifacts → END
```

| 节点               | 输入                                                                       | 输出                                         | LLM        |
| ------------------ | -------------------------------------------------------------------------- | -------------------------------------------- | ---------- |
| `analyze_gaps`     | `artifacts["extraction"]`, `artifacts["supervisor"]["research_direction"]` | `research_gaps: list[ResearchGap]`           | ✅          |
| `generate_designs` | `research_gaps`                                                            | `experiment_designs: list[ExperimentDesign]` | ✅          |
| `select_design`    | `experiment_designs`                                                       | `selected_design_index: int`                 | ✅ 排序推荐 |
| `write_artifacts`  | 全部私有字段                                                               | `artifacts["ideation"]`                      | ❌          |

### 关键实现细节

- **analyze_gaps**: 输入上游 extraction 笔记 + supervisor 研究方向。LLM 输出 `list[ResearchGap]`
- **generate_designs**: 为每个 gap 生成实验方案，每个方案含 hypothesis/baselines/datasets/metrics
- **select_design**: LLM 对方案排序打分，选出最优方案的 index

### 测试要点

- 验证三个 LLM 节点的输入/输出 schema
- 验证 `write_artifacts` 输出包含 `gaps`、`design`、`evaluation_metrics`

---

## Task 4: Execution WF — 沙箱验证

### 文件产出

| 文件                                            | 说明                           |
| ----------------------------------------------- | ------------------------------ |
| `backend/agent/workflows/execution/__init__.py` | 导出 `build_execution_graph`   |
| `backend/agent/workflows/execution/nodes.py`    | 6 个节点函数                   |
| `backend/agent/workflows/execution/graph.py`    | subgraph 编排（含循环 + HITL） |
| `backend/agent/prompts/execution/prompts.yaml`  | 2 个 prompt                    |
| `tests/unit/test_wf_execution.py`               | 单元测试                       |

### 节点设计

```
START → generate_code → request_confirmation(HITL) → execute_sandbox → [check_result]
     check_result:
       exit_code == 0 → write_artifacts → END
       budget_exceeded → write_artifacts(failure) → END
       otherwise → reflect_and_retry → generate_code (循环)
```

| 节点                   | 输入                                   | 输出                                       | LLM | 外部依赖                    |
| ---------------------- | -------------------------------------- | ------------------------------------------ | --- | --------------------------- |
| `generate_code`        | `task_description`, `reflection`(如有) | `generated_code: str`                      | ✅   | —                           |
| `request_confirmation` | `generated_code`                       | （HITL confirm）                           | ❌   | `interrupt()`               |
| `execute_sandbox`      | `generated_code`                       | `execution_result: SandboxExecutionResult` | ❌   | `sandbox_manager.execute()` |
| `reflect_and_retry`    | `execution_result`, `generated_code`   | `reflection: str`, `retry_count += 1`      | ✅   | —                           |
| `write_artifacts`      | 全部                                   | `artifacts["execution"]`                   | ❌   | —                           |

### 关键实现细节

- **条件边 `route_execution_result`**: 纯确定性判断（不调 LLM），使用 `check_loop_budget()` 检查四重预算
- **generate_code**: 首次传入 `task_description`；重试时额外传入 `reflection` + 上次 stderr
- **request_confirmation**: `interrupt({"action": "confirm_execute", "code": ..., "task": ...})`
- **execute_sandbox**: 调用 `sandbox_manager.execute()`，Phase 4 mock
- **reflect_and_retry**: LLM 分析失败原因，输出 `reflection` 字符串 + 递增 `retry_count`

### 测试要点

- mock sandbox → 验证成功路径（exit_code=0 → write_artifacts）
- mock sandbox → 验证失败重试路径（exit_code=1 → reflect → generate_code）
- mock sandbox → 验证预算超限路径（retry_count ≥ 3 → write_artifacts with failure）
- mock `interrupt()` → 验证 HITL resume

---

## Task 5: Critique WF — 模拟审稿

### 文件产出

| 文件                                           | 说明                          |
| ---------------------------------------------- | ----------------------------- |
| `backend/agent/workflows/critique/__init__.py` | 导出 `build_critique_graph`   |
| `backend/agent/workflows/critique/nodes.py`    | 4 个节点函数                  |
| `backend/agent/workflows/critique/graph.py`    | subgraph 编排（并行 fan-out） |
| `backend/agent/prompts/critique/prompts.yaml`  | 3 个 prompt                   |
| `tests/unit/test_wf_critique.py`               | 单元测试                      |

### 节点设计

```
START ─┬─ supporter_review ─┬─ judge_verdict → write_artifacts → END
       └─ critic_review ────┘
       (Send() 并行 fan-out)
```

| 节点              | 输入  | 输出                     | LLM |
| ----------------- | ----- | ------------------------ | --- |
| `fan_out_reviews` | State | `list[Send]`（两路并行） | ❌   |

> 注：`fan_out_reviews` 在实现中为 `_fan_out_reviews` 函数，通过 `add_conditional_edges(START, _fan_out_reviews)` 注册，功能等价。
| `supporter_review` | `artifacts[target_workflow]`          | `supporter_opinion: str`           | ✅   |
| `critic_review`    | `artifacts[target_workflow]`          | `critic_opinion: str`              | ✅   |
| `judge_verdict`    | `supporter_opinion`, `critic_opinion` | `verdict`, `feedbacks`             | ✅   |
| `write_artifacts`  | 全部                                  | `artifacts["critique"][target_wf]` | ❌   |

### 关键实现细节

- **fan_out_reviews**: `Send("supporter_review", state)` + `Send("critic_review", state)` 并行
- **supporter/critic**: 互不可见，各自独立调 LLM，避免锚定效应
- **judge_verdict**: 合并两方意见，LLM 输出 `verdict: "pass"|"revise"` + `feedbacks: list[CritiqueFeedback]`
- **write_artifacts**: 按 target_workflow 命名空间存储 `artifacts["critique"][target_wf]`
- **打回逻辑不在此 WF 内**——由 Supervisor `checkpoint_eval` 节点读取 verdict 并路由

### 测试要点

- mock LLM → 验证并行输出能正确合并到 judge_verdict
- 验证 `verdict="pass"` 和 `verdict="revise"` 两种路径
- 验证 artifacts 按 target_wf 命名空间隔离

---

## Task 6: Publish WF — 报告交付

### 文件产出

| 文件                                          | 说明                         |
| --------------------------------------------- | ---------------------------- |
| `backend/agent/workflows/publish/__init__.py` | 导出 `build_publish_graph`   |
| `backend/agent/workflows/publish/nodes.py`    | 6 个节点函数                 |
| `backend/agent/workflows/publish/graph.py`    | subgraph 编排（线性 + HITL） |
| `backend/agent/prompts/publish/prompts.yaml`  | 2 个 prompt                  |
| `tests/unit/test_wf_publish.py`               | 单元测试                     |

### 节点设计

```
START → assemble_outline → generate_markdown → request_finalization(HITL) → render_presentation → package_zip → write_artifacts → END
```

| 节点                   | 输入                    | 输出                                    | LLM | 外部依赖                            |
| ---------------------- | ----------------------- | --------------------------------------- | --- | ----------------------------------- |
| `assemble_outline`     | 全部上游 `artifacts`    | `outline: list[OutlineSection]`         | ✅   | —                                   |
| `generate_markdown`    | `outline` + `artifacts` | `markdown_content: str`, `citation_map` | ✅   | —                                   |
| `request_finalization` | `markdown_content`      | 可能更新 `markdown_content`             | ❌   | `interrupt()` HITL                  |
| `render_presentation`  | `markdown_content`      | `output_files` 追加 PDF                 | ❌   | ppt_generation Skill (Phase 4 mock) |
| `package_zip`          | 全部出物文件            | `output_files` 追加 .zip                | ❌   | —                                   |
| `write_artifacts`      | 全部                    | `artifacts["publish"]`                  | ❌   | —                                   |

### 关键实现细节

- **request_finalization HITL**:
  - `interrupt({"action": "confirm_finalize", "markdown_preview": ..., "outline": ...})`
  - approve → 继续
  - reject → 前端推送 Canvas 编辑，用户手改后 resume 传回 `{"modified_markdown": "..."}`
  - 收到 `modified_markdown` → 更新 `markdown_content` 再继续
- **render_presentation**: 调用 ppt_generation Skill（mode=subgraph），Phase 4 mock 为返回空列表
- **package_zip**: 收集所有 output_files 打包为 ZIP

### 测试要点

- mock LLM → 验证 `assemble_outline` 和 `generate_markdown` 输出格式
- mock interrupt → 验证 approve 路径和 reject+Canvas 回流路径
- 验证 `modified_markdown` 正确覆盖 `markdown_content`

---

## Task 7: 集成到 Supervisor 主图 + 填充 LLM 路由

### 修改文件

| 文件                                    | 修改内容                                                                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `backend/agent/graph.py`                | 用真实 subgraph 替换 `_placeholder_node`；填充 `_supervisor_node` LLM 路由逻辑；填充 `_checkpoint_eval_node` LLM 评估逻辑 |
| `backend/agent/prompts/supervisor.yaml` | 补充学科切换 snippet 占位                                                                                                 |
| `tests/unit/test_graph.py`              | 更新为覆盖真实 subgraph 注册                                                                                              |

### Supervisor 节点填充细节

```python
def supervisor_node(state: SupervisorState) -> dict:
    # 1. 硬规则检查
    hard_target = apply_hard_rules(state["messages"])
    if hard_target:
        return {"routing_decision": hard_target, "plan": None, "current_step_index": 0}

    # 2. LLM 结构化输出路由
    decision = llm.with_structured_output(RouteDecision).invoke(...)

    # 3. 根据 mode (single/plan) 返回路由结果
```

### checkpoint_eval 节点填充细节

```python
def checkpoint_eval_node(state: SupervisorState) -> dict:
    # 1. 检查 critique verdict (打回逻辑)
    # 2. LLM 轻量评估 success_criteria
    # 3. passed → 路由到下一步 / __end__
    # 4. failed → __replan__ → 回到 supervisor
```

### 测试要点

- mock LLM → 验证 `supervisor_node` 的 single/plan 两种路由模式
- mock LLM → 验证 `checkpoint_eval` 的 pass/revise/replan 三种路径
- 端到端 mock 测试：discovery → extraction → ideation 三步计划执行

---

## 验证清单（汇总）

| 检查项          | 命令                                                | 期望     |
| --------------- | --------------------------------------------------- | -------- |
| Discovery WF    | `uv run pytest tests/unit/test_wf_discovery.py -v`  | passed   |
| Extraction WF   | `uv run pytest tests/unit/test_wf_extraction.py -v` | passed   |
| Ideation WF     | `uv run pytest tests/unit/test_wf_ideation.py -v`   | passed   |
| Execution WF    | `uv run pytest tests/unit/test_wf_execution.py -v`  | passed   |
| Critique WF     | `uv run pytest tests/unit/test_wf_critique.py -v`   | passed   |
| Publish WF      | `uv run pytest tests/unit/test_wf_publish.py -v`    | passed   |
| Supervisor 集成 | `uv run pytest tests/unit/test_graph.py -v`         | passed   |
| 全量 lint       | `uv run ruff check backend/agent/workflows/`        | 0 errors |
