"""DSPy 编译模块层。提供 ModuleRegistry 单例和各 DSPy Module 定义。"""

from backend.agent.dspy_modules.registry import ModuleRegistry

registry = ModuleRegistry()

__all__ = ["ModuleRegistry", "registry"]
