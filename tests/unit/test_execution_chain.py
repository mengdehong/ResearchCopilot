"""Execution WF 全链路测试。

编译完整的 Execution 子图，端到端验证循环 + HITL + 条件边：
  成功路径：generate_code → request_confirmation (approve) → execute_sandbox → write_artifacts
  重试路径：generate_code → HITL → execute_sandbox (fail) → reflect_and_retry → ... → write_artifacts

LLM / interrupt 使用 mock，验证条件边路由和 retry_count 递增。
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.agent.workflows.execution.graph import build_execution_graph
from backend.agent.workflows.execution.nodes import (
    GeneratedCode,
    ReflectionResult,
)


def _build_mock_llm_success() -> MagicMock:
    """构建 mock LLM：一次生成成功代码。"""
    responses = [
        GeneratedCode(code="import numpy as np\nprint(np.pi)", description="Print pi"),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _build_mock_llm_retry() -> MagicMock:
    """构建 mock LLM：第一次生成 → 失败 → 反思 → 第二次生成 → 成功。"""
    responses = [
        # generate_code (第一次)
        GeneratedCode(code="broken code", description="Has bug"),
        # reflect_and_retry
        ReflectionResult(
            root_cause="NameError: undefined variable",
            fix_strategy="Define the variable before use",
            revised_code="x = 42\nprint(x)",
        ),
        # generate_code 不会被再次调用 — reflect_and_retry 直接写 generated_code
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.asyncio
@patch("backend.agent.workflows.execution.nodes.interrupt")
async def test_execution_chain_success(mock_interrupt: MagicMock) -> None:
    """成功路径：approve → execute (exit_code=0) → write_artifacts。"""
    mock_interrupt.return_value = None  # approve

    llm = _build_mock_llm_success()
    graph = build_execution_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {"ideation": {"experiment_design": {"hypothesis": "test"}}},
        "task_description": "Run pi calculation",
        "retry_count": 0,
        "elapsed_seconds": 0.0,
        "tokens_used": 0,
    }

    result = await compiled.ainvoke(input_state)

    # ── 验证 HITL interrupt ──
    mock_interrupt.assert_called_once()

    # ── 验证 artifacts ──
    execution = result["artifacts"]["execution"]
    assert execution["results"]["success"] is True
    assert execution["results"]["exit_code"] == 0
    assert execution["retry_count"] == 0
    assert "numpy" in execution["code"] or "print" in execution["code"]


@pytest.mark.asyncio
@patch("backend.agent.workflows.execution.nodes.interrupt")
async def test_execution_chain_reject(mock_interrupt: MagicMock) -> None:
    """拒绝路径：reject → 跳过 sandbox → write_artifacts (无 execution_result)。"""
    mock_interrupt.return_value = {"decision": "reject"}

    llm = _build_mock_llm_success()
    graph = build_execution_graph(llm=llm)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {"ideation": {}},
        "task_description": "Dangerous operation",
        "retry_count": 0,
        "elapsed_seconds": 0.0,
        "tokens_used": 0,
    }

    result = await compiled.ainvoke(input_state)

    execution = result["artifacts"]["execution"]
    # reject 时 execution_result 为 None，success = False
    assert execution["results"]["success"] is False
    assert execution["results"]["exit_code"] == -1


@pytest.mark.asyncio
@patch("backend.agent.workflows.execution.nodes.interrupt")
async def test_execution_chain_retry_loop(mock_interrupt: MagicMock) -> None:
    """重试路径：fail → reflect → 循环回 generate_code → succeed → write_artifacts。

    使用自定义 executor mock 来控制 exit_code 序列。
    """
    mock_interrupt.return_value = None  # approve

    # 构建 LLM: generate_code 第一次 → reflect_and_retry → generate_code 第二次
    responses = [
        # generate_code (第一次)
        GeneratedCode(code="broken", description="buggy"),
        # reflect_and_retry
        ReflectionResult(
            root_cause="SyntaxError",
            fix_strategy="Fix syntax",
            revised_code="print('fixed')",
        ),
        # generate_code (第二次 — 由 reflect_and_retry 循环回来后自动触发)
        # 但 reflect_and_retry 直接设置 generated_code，所以 generate_code 会被再次调用
        GeneratedCode(code="print('fixed v2')", description="fixed"),
    ]
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)

    # 自定义 executor：第一次 fail，后续 success
    call_count = {"n": 0}
    mock_executor = MagicMock()

    def _mock_execute(req: object) -> MagicMock:
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.exit_code = 1
            result.stdout = ""
            result.stderr = "SyntaxError"
            result.output_files = {}
        else:
            result.exit_code = 0
            result.stdout = "fixed"
            result.stderr = ""
            result.output_files = {}
        return result

    mock_executor.execute = _mock_execute

    graph = build_execution_graph(llm=llm, executor=mock_executor)
    compiled = graph.compile()

    input_state = {
        "messages": [],
        "workspace_id": "ws-test",
        "discipline": "cs",
        "artifacts": {"ideation": {}},
        "task_description": "Test retry",
        "retry_count": 0,
        "elapsed_seconds": 0.0,
        "tokens_used": 0,
    }

    result = await compiled.ainvoke(input_state)

    execution = result["artifacts"]["execution"]
    assert execution["results"]["success"] is True
    assert execution["retry_count"] >= 1
