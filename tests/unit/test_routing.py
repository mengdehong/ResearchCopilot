"""Routing 逻辑测试。"""

from unittest.mock import MagicMock

import pytest

from backend.agent.routing import (
    RouteDecision,
    apply_hard_rules,
    route_after_eval,
    route_to_workflow,
)


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


def test_route_to_workflow_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid routing_decision"):
        route_to_workflow({"routing_decision": "typo"})


def test_route_after_eval_replan() -> None:
    assert route_after_eval({"routing_decision": "__replan__"}) == "supervisor"


def test_route_after_eval_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid routing_decision"):
        route_after_eval({"routing_decision": "typo"})


def test_route_decision_chat_mode() -> None:
    """RouteDecision 支持 mode=chat + reply_text。"""
    decision = RouteDecision(
        mode="chat",
        reasoning="用户在打招呼",
        reply_text="你好，我是 Research Copilot！",
    )
    assert decision.mode == "chat"
    assert decision.reply_text == "你好，我是 Research Copilot！"
    assert decision.target_workflow is None


def test_route_to_workflow_chat_routes_to_end() -> None:
    """__chat__ 路由决策应该映射到 __end__。"""
    assert route_to_workflow({"routing_decision": "__chat__"}) == "__end__"
