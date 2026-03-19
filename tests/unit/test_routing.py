"""Routing 逻辑测试。"""
from unittest.mock import MagicMock

from backend.agent.routing import apply_hard_rules, route_after_eval, route_to_workflow


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


def test_route_after_eval_replan() -> None:
    assert route_after_eval({"routing_decision": "__replan__"}) == "supervisor"
