"""Skill 注册中心。发现、注册和调度技能。"""

from backend.agent.skills.base import SkillDefinition
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """技能注册中心。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        """注册一个 Skill。"""
        if skill.name in self._skills:
            logger.warning("skill_already_registered", name=skill.name)
        self._skills[skill.name] = skill
        logger.info("skill_registered", name=skill.name)

    def get(self, name: str) -> SkillDefinition:
        """按名称获取 Skill。"""
        if name not in self._skills:
            raise KeyError(f"Skill not found: {name}")
        return self._skills[name]

    def list_skills(self) -> list[SkillDefinition]:
        """列出所有已注册 Skill。"""
        return list(self._skills.values())

    def search_by_tag(self, tag: str) -> list[SkillDefinition]:
        """按标签搜索 Skill。"""
        return [s for s in self._skills.values() if tag in s.tags]
