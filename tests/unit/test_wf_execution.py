"""Execution WF 单元测试。"""
from unittest.mock import MagicMock, patch

from backend.agent.state import SandboxExecutionResult
from backend.agent.workflows.execution.graph import build_execution_graph
from backend.agent.workflows.execution.nodes import (
    GeneratedCode,
    ReflectionResult,
    execute_sandbox,
    generate_code,
    reflect_and_retry,
    route_execution_result,
    write_artifacts,
)


def _make_mock_llm(responses: list) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke = MagicMock(side_effect=responses)
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_exec_result(exit_code: int = 0, **overrides: object) -> SandboxExecutionResult:
    defaults = {
        "exit_code": exit_code,
        "stdout": "ok",
        "stderr": "",
        "output_files": [],
        "execution_time_seconds": 1.0,
    }
    defaults.update(overrides)
    return SandboxExecutionResult(**defaults)


# ── generate_code ──

def test_generate_code_returns_code() -> None:
    llm = _make_mock_llm([GeneratedCode(code="print('hi')", description="test")])
    state = {
        "task_description": "run experiment",
        "reflection": None,
        "artifacts": {"ideation": {}},
    }
    result = generate_code(state, llm=llm)
    assert "print" in result["generated_code"]


# ── execute_sandbox ──

def test_execute_sandbox_returns_result() -> None:
    state = {"generated_code": "print('hi')", "elapsed_seconds": 0.0}
    result = execute_sandbox(state)
    assert result["execution_result"].exit_code == 0


# ── route_execution_result ──

def test_route_success() -> None:
    state = {"execution_result": _make_exec_result(exit_code=0)}
    assert route_execution_result(state) == "write_artifacts"


def test_route_failure_with_budget() -> None:
    state = {
        "execution_result": _make_exec_result(exit_code=1),
        "retry_count": 0,
        "elapsed_seconds": 0.0,
        "tokens_used": 0,
    }
    assert route_execution_result(state) == "reflect_and_retry"


def test_route_budget_exceeded() -> None:
    state = {
        "execution_result": _make_exec_result(exit_code=1),
        "retry_count": 10,  # 超限
        "elapsed_seconds": 0.0,
        "tokens_used": 0,
    }
    assert route_execution_result(state) == "write_artifacts"


def test_route_no_result() -> None:
    state = {"execution_result": None}
    assert route_execution_result(state) == "write_artifacts"


# ── reflect_and_retry ──

def test_reflect_and_retry_increments_count() -> None:
    llm = _make_mock_llm([
        ReflectionResult(
            root_cause="syntax error",
            fix_strategy="fix syntax",
            revised_code="print('fixed')",
        ),
    ])
    state = {
        "execution_result": _make_exec_result(exit_code=1, stderr="SyntaxError"),
        "generated_code": "broken code",
        "retry_count": 0,
    }
    result = reflect_and_retry(state, llm=llm)
    assert result["retry_count"] == 1
    assert "fixed" in result["generated_code"]


# ── write_artifacts ──

def test_execution_write_artifacts_success() -> None:
    state = {
        "execution_result": _make_exec_result(exit_code=0),
        "generated_code": "code",
        "retry_count": 0,
    }
    result = write_artifacts(state)
    assert result["artifacts"]["execution"]["results"]["success"] is True


def test_execution_write_artifacts_failure() -> None:
    state = {
        "execution_result": _make_exec_result(exit_code=1),
        "generated_code": "code",
        "retry_count": 2,
    }
    result = write_artifacts(state)
    assert result["artifacts"]["execution"]["results"]["success"] is False


# ── request_confirmation (HITL) ──

def test_request_confirmation_calls_interrupt() -> None:
    state = {"generated_code": "code", "task_description": "task"}
    with patch(
        "backend.agent.workflows.execution.nodes.interrupt",
        return_value=None,
    ):
        from backend.agent.workflows.execution.nodes import request_confirmation
        result = request_confirmation(state)
        assert result == {}


# ── Subgraph 编译 ──

def test_execution_graph_compiles() -> None:
    llm = MagicMock()
    graph = build_execution_graph(llm=llm)
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "generate_code" in node_names
    assert "execute_sandbox" in node_names
    assert "reflect_and_retry" in node_names
