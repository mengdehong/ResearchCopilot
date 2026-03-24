"""Critique 打回上游 WF 重注入循环测试。测试 _handle_critique_revise 纯函数。"""

import pytest

from backend.agent.graph import _handle_critique_revise

# ── verdict=revise → 返回 target WF 路由 + revision_context ──


@pytest.mark.unit
def test_revise_returns_target_wf_and_context() -> None:
    """verdict=revise 时应返回目标 WF 路由和 revision_context。"""
    critique_results = {
        "extraction": {
            "verdict": "revise",
            "round": 1,
            "feedbacks": [
                {
                    "severity": "major",
                    "category": "methodology",
                    "description": "Missing baseline",
                    "suggestion": "Add ablation study",
                },
            ],
        },
    }
    result = _handle_critique_revise(critique_results, max_rounds=2)
    assert result is not None
    assert result["routing_decision"] == "extraction"
    assert result["critique_round"] == 2
    assert result["revision_context"]  # 非空反馈文本
    assert "Missing baseline" in result["revision_context"]
    assert result["plan"] is None
    assert result["artifacts"]["critique"]["extraction"]["verdict"] == "revision_in_progress"


# ── max rounds → 跳过 revise ──


@pytest.mark.unit
def test_revise_max_rounds_skips() -> None:
    """达到最大轮数时应跳过 revise，返回 None。"""
    critique_results = {
        "extraction": {
            "verdict": "revise",
            "round": 2,
            "feedbacks": [],
        },
    }
    result = _handle_critique_revise(critique_results, max_rounds=2)
    assert result is None


# ── verdict=pass → 不触发 ──


@pytest.mark.unit
def test_pass_verdict_returns_none() -> None:
    """verdict=pass 时不应触发 revise。"""
    critique_results = {
        "extraction": {
            "verdict": "pass",
            "round": 1,
            "feedbacks": [],
        },
    }
    result = _handle_critique_revise(critique_results, max_rounds=2)
    assert result is None


# ── revision_in_progress → 不触发二次处理 ──


@pytest.mark.unit
def test_revision_in_progress_returns_none() -> None:
    """revision_in_progress 状态不应触发二次处理。"""
    critique_results = {
        "extraction": {
            "verdict": "revision_in_progress",
        },
    }
    result = _handle_critique_revise(critique_results, max_rounds=2)
    assert result is None


# ── 空 critique_results → 返回 None ──


@pytest.mark.unit
def test_empty_critique_results_returns_none() -> None:
    """空 critique_results 应返回 None。"""
    result = _handle_critique_revise({}, max_rounds=2)
    assert result is None


# ── messages 包含修订指令 ──


@pytest.mark.unit
def test_revise_includes_revision_message() -> None:
    """revise 结果应包含修订指令消息。"""
    critique_results = {
        "ideation": {
            "verdict": "revise",
            "round": 1,
            "feedbacks": [
                {
                    "severity": "minor",
                    "category": "clarity",
                    "description": "Unclear hypothesis",
                    "suggestion": "Reword hypothesis",
                },
            ],
        },
    }
    result = _handle_critique_revise(critique_results, max_rounds=3)
    assert result is not None
    assert len(result["messages"]) == 1
    msg = result["messages"][0]
    assert "ideation" in msg.content
    assert "Unclear hypothesis" in result["revision_context"]
