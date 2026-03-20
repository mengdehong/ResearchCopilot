"""Prompt Loader 测试。"""

import pytest

from backend.agent.prompts.loader import load_prompt


def test_load_supervisor_prompt() -> None:
    result = load_prompt(
        "supervisor",
        variables={
            "discipline": "computer_science",
            "user_message": "搜索 transformer 相关论文",
            "artifacts_summary": "{}",
        },
    )
    assert "Supervisor" in result["system"]
    assert "搜索 transformer" in result["user"]


def test_load_nonexistent_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent")
