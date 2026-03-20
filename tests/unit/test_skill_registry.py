"""Skill Registry 测试。"""
import pytest

from backend.agent.skills.base import SkillDefinition
from backend.agent.skills.registry import SkillRegistry


def test_register_and_get() -> None:
    registry = SkillRegistry()
    skill = SkillDefinition(
        name="arxiv_search", description="Search Arxiv",
        input_schema={"query": "str"}, output_schema={"results": "list"},
        tags=["search", "discovery"],
    )
    registry.register(skill)
    assert registry.get("arxiv_search") == skill


def test_get_nonexistent_raises() -> None:
    registry = SkillRegistry()
    with pytest.raises(KeyError, match="not found"):
        registry.get("nonexistent")


def test_search_by_tag() -> None:
    registry = SkillRegistry()
    registry.register(SkillDefinition(
        name="s1", description="", input_schema={}, output_schema={}, tags=["search"],
    ))
    registry.register(SkillDefinition(
        name="s2", description="", input_schema={}, output_schema={}, tags=["compute"],
    ))
    results = registry.search_by_tag("search")
    assert len(results) == 1
    assert results[0].name == "s1"
