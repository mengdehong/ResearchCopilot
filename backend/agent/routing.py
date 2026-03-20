"""Supervisor 路由逻辑。硬规则门禁 + LLM 路由 + 检查点回评。"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from backend.agent.state import ExecutionPlan, WorkflowName
from backend.core.logger import get_logger

logger = get_logger(__name__)

VALID_WORKFLOWS = frozenset(
    {
        "discovery",
        "extraction",
        "ideation",
        "execution",
        "critique",
        "publish",
    }
)


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
            logger.info("hard_rule_matched", rule_name=rule.name, target=rule.target)
            return rule.target
    return None


class RouteDecision(BaseModel):
    """LLM 路由决策输出。"""

    mode: Literal["single", "plan"]
    target_workflow: WorkflowName | None = None
    plan: ExecutionPlan | None = None
    reasoning: str


class StepEvaluation(BaseModel):
    """检查点回评结果。"""

    passed: bool
    reason: str
    suggestion: str | None = None


def route_to_workflow(state: dict) -> str:
    """根据 routing_decision 路由到目标 WF。无效名称抛出 ValueError。"""
    decision = state.get("routing_decision")
    if decision is None or decision == "__end__":
        return "__end__"
    if decision in VALID_WORKFLOWS:
        return decision
    raise ValueError(f"Invalid routing_decision: {decision!r}, valid: {sorted(VALID_WORKFLOWS)}")


def route_after_eval(state: dict) -> str:
    """检查点回评后的路由。无效名称抛出 ValueError。"""
    decision = state.get("routing_decision")
    if decision == "__end__":
        return "__end__"
    if decision == "__replan__":
        return "supervisor"
    if decision in VALID_WORKFLOWS:
        return decision
    raise ValueError(f"Invalid routing_decision: {decision!r}, valid: {sorted(VALID_WORKFLOWS)}")
