"""Supervisor 路由加权评分函数。

DSPy metric 函数签名: (example, pred, trace=None) -> float
"""

from backend.agent.routing import RouteDecision
from backend.core.logger import get_logger

logger = get_logger(__name__)


def supervisor_routing_metric(
    example: object,
    pred: object,
    trace: object = None,
) -> float:
    """计算 Supervisor 路由的精准度得分。

    评分规则:
        1. Mode 匹配 (权重 0.4) — 模式错了直接 0 分
        2. Workflow 目标匹配 (单路径 single 下权重 0.6)
        3. 计划路径合理性 (plan 下权重 0.6: 首步 WF 0.3 + 步数接近 0.3)

    Args:
        example: DSPy Example，含 routing_decision 字段。
        pred: 模型预测的 DSPy Example。
        trace: DSPy trace（编译时用，此处忽略）。

    Returns:
        0.0 ~ 1.0 的得分。
    """
    expected: RouteDecision = example.routing_decision  # type: ignore[union-attr]
    # DSPy v3: pred 可能是 Prediction(routing_decision=...) 也可能是直接的 RouteDecision
    if hasattr(pred, "routing_decision"):
        predicted: RouteDecision = pred.routing_decision  # type: ignore[union-attr]
    elif isinstance(pred, RouteDecision):
        predicted = pred
    else:
        return 0.0

    # 1. Mode 匹配（权重 0.4）
    if expected.mode != predicted.mode:
        return 0.0

    score = 0.4

    # 2. Workflow 目标匹配（single 模式下权重 0.6）
    if expected.mode == "single":
        if expected.target_workflow == predicted.target_workflow:
            score += 0.6

    # 3. 计划路径合理性（plan 模式下权重 0.6）
    elif expected.mode == "plan":
        if expected.plan and predicted.plan and expected.plan.steps and predicted.plan.steps:
            # 首步 workflow 匹配 → 0.3
            if expected.plan.steps[0].workflow == predicted.plan.steps[0].workflow:
                score += 0.3
            # 步数接近（差 ±1 内）→ 0.3
            if abs(len(expected.plan.steps) - len(predicted.plan.steps)) <= 1:
                score += 0.3

    # chat 模式只要 mode 对了就给 0.4 + 0.6 bonus
    elif expected.mode == "chat":
        score += 0.6

    return score
