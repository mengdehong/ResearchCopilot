# Phase 4: Agent Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 实现 6 个专家工作流（Discovery → Extraction → Ideation → Execution → Critique → Publish），替换 Phase 3 中的 placeholder 节点。

**Architecture:** 每个 WF 在 `backend/agent/workflows/{N}_{name}/` 下独立实现，包含 state.py（已在 Phase 3 定义，此处导入）、nodes.py（节点函数）、graph.py（subgraph 编排）。

**前置条件：** Phase 3 Agent Core 完成

**对应设计文档：**
- [Agent 设计 §三](file:///home/wenmou/Projects/ResearchCopilot/docs/superpowers/specs/2026-03-19-langgraph-agent-design.md) — 各 WF 内部节点编排

---

## 文件结构

```
backend/agent/workflows/
├── __init__.py
├── 1_discovery/
│   ├── __init__.py
│   ├── nodes.py       # expand_query, search_apis, filter_and_rank, present_candidates(HITL), trigger_ingestion, write_artifacts
│   └── graph.py       # Discovery subgraph (线性 + HITL)
├── 2_extraction/
│   ├── __init__.py
│   ├── nodes.py       # wait_rag_ready, retrieve_chunks, generate_notes, cross_compare, build_glossary
│   └── graph.py       # Extraction subgraph (线性)
├── 3_ideation/
│   ├── __init__.py
│   ├── nodes.py       # analyze_gaps, generate_designs, select_design
│   └── graph.py       # Ideation subgraph (线性)
├── 4_execution/
│   ├── __init__.py
│   ├── nodes.py       # generate_code, request_confirmation(HITL), execute_sandbox, reflect_and_retry
│   └── graph.py       # Execution subgraph (循环 + HITL)
├── 5_critique/
│   ├── __init__.py
│   ├── nodes.py       # supporter_review, critic_review, judge_verdict
│   └── graph.py       # Critique subgraph (并行 fan-out, 红蓝对抗)
└── 6_publish/
    ├── __init__.py
    ├── nodes.py       # assemble_outline, generate_markdown, request_finalization(HITL), render_pptx, package_zip
    └── graph.py       # Publish subgraph (线性 + HITL)
```

---

## Task 1: Discovery WF — 寻源初筛

> 线性+HITL：`expand_query → search_apis → filter_and_rank → present_candidates(HITL) → trigger_ingestion → write_artifacts`。用户勾选论文后仅对选中论文触发 ingestion。

- [ ] **Step 1: 实现 nodes.py** — 6 个节点函数：expand_query、search_apis、filter_and_rank（含 LLM 生成 relevance_comment）、present_candidates（`interrupt()` 展示候选列表供用户勾选）、trigger_ingestion（调 BFF document service 仅处理选中论文）、write_artifacts
- [ ] **Step 2: 实现 graph.py** — `StateGraph(DiscoveryState, input=SharedState, output=SharedState)` 线性+HITL 编排
- [ ] **Step 3: 编写测试** — `tests/unit/test_wf_discovery.py`，mock LLM 和 API 调用，测试 HITL resume 路径
- [ ] **Step 4: Commit**

---

## Task 2: Extraction WF — 深度精读

> 线性流程（含增量检查）：`wait_rag_ready → check_existing_notes → retrieve_chunks → generate_notes → cross_compare → build_glossary → write_artifacts`

- [ ] **Step 1: 实现 nodes.py** — wait_rag_ready 轮询文档解析状态；check_existing_notes 增量检查跳过已有笔记的论文；其余节点调用 RAG Engine 和 LLM
- [ ] **Step 2: 实现 graph.py** — 线性编排
- [ ] **Step 3: 编写测试** — mock RAGEngine.retrieve 和 LLM
- [ ] **Step 4: Commit**

---

## Task 3: Ideation WF — 实验推演

> 线性流程：`analyze_gaps → generate_designs → select_design → write_artifacts`

- [ ] **Step 1: 实现 nodes.py** — LLM 分析 Gap、生成方案、推荐排序
- [ ] **Step 2: 实现 graph.py** — 线性编排
- [ ] **Step 3: 编写测试**
- [ ] **Step 4: Commit**

---

## Task 4: Execution WF — 沙箱验证（循环 + HITL）

> 循环流程：`generate_code → request_confirmation(HITL) → execute_sandbox → check_result → [reflect_and_retry → generate_code | write_artifacts]`

关键设计点：
- `request_confirmation` 使用 `interrupt()` 挂起等待用户确认
- `check_result` 使用确定性条件边（检查 exit_code + budget）
- 循环退出使用 `check_loop_budget` 四重保障
- `execute_sandbox` 调用 `DockerExecutor.execute()`

- [ ] **Step 1: 实现 nodes.py** — 含 HITL interrupt 和 budget check
- [ ] **Step 2: 实现 graph.py** — 含条件边和循环
- [ ] **Step 3: 编写测试** — mock sandbox executor，测试成功/失败/预算超限三种路径
- [ ] **Step 4: Commit**

---

## Task 5: Critique WF — 模拟审稿（红蓝并行对抗）

> 并行 fan-out：`START ─┬─ supporter_review ─┬─ judge_verdict → write_artifacts → END`
>                 `└─ critic_review ───┘`（并行，互不可见）

关键设计点：
- 支持者和批评者使用 `Send()` **并行执行**，互不可见，避免锚定效应
- 裁决节点合并两方意见，输出 `verdict: "pass" | "revise"` + `feedbacks`
- artifacts 按审查目标分命名空间存储：`artifacts["critique"][target_wf]`
- 打回逻辑由 Supervisor 的 checkpoint_eval 处理，不在此 WF 内

- [ ] **Step 1: 实现 nodes.py** — 支持者和批评者独立 LLM 调用 + 裁决者合并裁决
- [ ] **Step 2: 实现 graph.py** — `fan_out_reviews` 使用 `Send()` 并行 fan-out 编排
- [ ] **Step 3: 编写测试** — mock LLM，验证并行输出合并和 verdict 结果
- [ ] **Step 4: Commit**

---

## Task 6: Publish WF — 报告交付（含 HITL + Canvas 回流）

> 线性 + HITL 分支：`assemble_outline → generate_markdown → request_finalization(HITL) → render_pptx → package_zip → write_artifacts`
> HITL 分支：approve→继续 / reject→推送至 Canvas 编辑器用户手改→确认后回流（modified_markdown）

关键设计点：
- `request_finalization` 使用 `interrupt()` 展示 Markdown 预览
- approve 直接继续；reject 时前端将 Markdown 推送到 Canvas，用户手改后确认定稿，将 `modified_markdown` 发送 resume
- 收到 `modified_markdown` 后更新 `markdown_content` 再继续渲染
- `render_pptx` 调用 PPT 生成 Skill（或 python-pptx 模板引擎）

- [ ] **Step 1: 实现 nodes.py** — 含 HITL interrupt（approve/reject 双路径）和 PPTX 渲染
- [ ] **Step 2: 实现 graph.py** — 线性编排 + HITL
- [ ] **Step 3: 编写测试** — 测试 approve 和 reject+Canvas 回流两种路径
- [ ] **Step 4: Commit**

---

## Task 7: 集成到 Supervisor 主图

- [ ] **Step 1: 更新 graph.py** — 用真实 WF subgraph 替换 placeholder 节点
- [ ] **Step 2: 更新 Supervisor 节点** — 填充 LLM 路由和检查点回评逻辑
- [ ] **Step 3: 编写端到端测试** — mock LLM，验证完整流程 discovery → extraction → ideation
- [ ] **Step 4: Commit**

---

## 验证清单

| 检查项        | 命令                                                | 期望结果 |
| ------------- | --------------------------------------------------- | -------- |
| Discovery WF  | `uv run pytest tests/unit/test_wf_discovery.py -v`  | passed   |
| Extraction WF | `uv run pytest tests/unit/test_wf_extraction.py -v` | passed   |
| Ideation WF   | `uv run pytest tests/unit/test_wf_ideation.py -v`   | passed   |
| Execution WF  | `uv run pytest tests/unit/test_wf_execution.py -v`  | passed   |
| Critique WF   | `uv run pytest tests/unit/test_wf_critique.py -v`   | passed   |
| Publish WF    | `uv run pytest tests/unit/test_wf_publish.py -v`    | passed   |
| 全量 lint     | `uv run ruff check backend/agent/workflows/`        | 0 errors |

---

**Phase 4 完成标志：** 6 个 WF subgraph 全部实现 + 集成到 Supervisor 主图 + 单元测试通过 → 可进入 Phase 5。
