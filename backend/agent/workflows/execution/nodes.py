"""Execution WF 节点函数。沙箱验证：生成代码 → HITL 确认 → 执行 → 反思重试/写 artifacts。"""

import json
import time
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.services.sandbox_manager import CodeExecutor

from backend.agent.budget import EXECUTION_BUDGET, check_loop_budget
from backend.agent.prompts.loader import load_prompt
from backend.agent.state import ExecutionState, SandboxExecutionResult
from backend.core.logger import get_logger

logger = get_logger(__name__)


# ── LLM 输出结构 ──

class GeneratedCode(BaseModel):
    """LLM 生成的实验代码。"""
    code: str
    description: str


class ReflectionResult(BaseModel):
    """LLM 反思分析结果。"""
    root_cause: str
    fix_strategy: str
    revised_code: str


# ── 节点函数 ──

def generate_code(
    state: ExecutionState, *, llm: BaseChatModel,
) -> dict:
    """LLM 生成实验代码。"""
    task_desc = state.get("task_description", "")
    artifacts = state.get("artifacts", {})
    ideation = artifacts.get("ideation", {})
    reflection = state.get("reflection")

    prompt_parts = [
        f"实验任务: {task_desc}",
        f"实验方案: {json.dumps(ideation.get('experiment_design', {}), ensure_ascii=False)}",
    ]
    if reflection:
        prompt_parts.append(f"上次执行失败原因及修正策略:\n{reflection}")

    result = llm.with_structured_output(GeneratedCode).invoke([
        SystemMessage(content=load_prompt(
            "execution/prompts", key="generate_code",
            variables={"prompt_parts": ""},
        )["system"]),
        HumanMessage(content="\n".join(prompt_parts)),
    ])

    logger.info("generate_code_done", code_length=len(result.code))
    return {"generated_code": result.code}


def request_confirmation(state: ExecutionState) -> dict:
    """独立 HITL 节点：展示代码，等待用户确认执行。"""
    interrupt({
        "action": "confirm_execute",
        "code": state.get("generated_code", ""),
        "task": state.get("task_description", ""),
    })
    return {}


def execute_sandbox(
    state: ExecutionState,
    *,
    executor: "CodeExecutor | None" = None,
) -> dict:
    """调用沙箱执行代码。

    当 executor 被注入时调用真实执行器；否则保持占位行为。
    """
    code = state.get("generated_code", "")
    start = time.monotonic()

    if executor is not None:
        from backend.services.sandbox_manager import ExecutionRequest
        exec_result = executor.execute(ExecutionRequest(code=code))
        elapsed = time.monotonic() - start
        result = SandboxExecutionResult(
            exit_code=exec_result.exit_code,
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            output_files=list(exec_result.output_files.keys()),
            execution_time_seconds=elapsed,
        )
    else:
        # Phase 4 占位：模拟成功
        elapsed = time.monotonic() - start
        result = SandboxExecutionResult(
            exit_code=0,
            stdout="Execution placeholder - success",
            stderr="",
            output_files=[],
            execution_time_seconds=elapsed,
        )

    logger.info(
        "execute_sandbox_done",
        exit_code=result.exit_code,
        duration_s=result.execution_time_seconds,
        mode="real" if executor else "placeholder",
    )
    return {
        "execution_result": result,
        "elapsed_seconds": state.get("elapsed_seconds", 0.0) + elapsed,
    }



def route_execution_result(state: ExecutionState) -> str:
    """确定性路由：检查执行结果和预算。"""
    result = state.get("execution_result")
    if result is None:
        return "write_artifacts"

    if result.exit_code == 0:
        return "write_artifacts"

    budget_reason = check_loop_budget(
        state.get("retry_count", 0),
        state.get("elapsed_seconds", 0.0),
        state.get("tokens_used", 0),
        EXECUTION_BUDGET,
    )
    if budget_reason:
        logger.info("execution_budget_exceeded", reason=budget_reason)
        return "write_artifacts"

    return "reflect_and_retry"


def reflect_and_retry(
    state: ExecutionState, *, llm: BaseChatModel,
) -> dict:
    """LLM 分析失败原因，生成修正代码。"""
    result = state.get("execution_result")
    code = state.get("generated_code", "")

    reflection = llm.with_structured_output(ReflectionResult).invoke([
        SystemMessage(content=load_prompt(
            "execution/prompts", key="reflect_and_retry",
            variables={"error_context": ""},
        )["system"]),
        HumanMessage(content=json.dumps({
            "code": code,
            "exit_code": result.exit_code if result else -1,
            "stdout": result.stdout if result else "",
            "stderr": result.stderr if result else "",
        }, ensure_ascii=False)),
    ])

    logger.info("reflect_and_retry", root_cause=reflection.root_cause)
    return {
        "reflection": f"Root cause: {reflection.root_cause}\nFix: {reflection.fix_strategy}",
        "generated_code": reflection.revised_code,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def write_artifacts(state: ExecutionState) -> dict:
    """将 Execution 产出物写入 artifacts 命名空间。"""
    result = state.get("execution_result")
    success = result is not None and result.exit_code == 0

    return {
        "artifacts": {
            "execution": {
                "code": state.get("generated_code", ""),
                "results": {
                    "success": success,
                    "exit_code": result.exit_code if result else -1,
                    "stdout": result.stdout if result else "",
                    "stderr": result.stderr if result else "",
                },
                "output_files": result.output_files if result else [],
                "retry_count": state.get("retry_count", 0),
            },
        },
    }
