"""Prompt 加载器。YAML 基线 + DB 覆盖层。"""
from pathlib import Path

import yaml

from backend.core.logger import get_logger

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, *, variables: dict[str, str] | None = None) -> dict[str, str]:
    """加载 prompt。先找 YAML 文件，变量替换后返回 system + user。

    Args:
        name: prompt 名称（不含 .yaml 后缀）。
        variables: 模板变量替换映射。

    Returns:
        {"system": "...", "user": "..."} 替换变量后的 prompt。
    """
    yaml_path = PROMPTS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    system_template: str = data.get("system", "")
    user_template: str = data.get("user", "")
    variables = variables or {}

    return {
        "system": system_template.format(**variables) if variables else system_template,
        "user": user_template.format(**variables) if variables else user_template,
    }
