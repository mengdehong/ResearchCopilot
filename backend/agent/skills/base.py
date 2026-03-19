"""Skill 基类定义。"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillDefinition:
    """技能定义。从 skill.yaml 加载。"""
    name: str
    description: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    tags: list[str] = field(default_factory=list)
    execute: Callable[..., Any] | None = None
