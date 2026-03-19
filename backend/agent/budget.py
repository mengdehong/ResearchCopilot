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
