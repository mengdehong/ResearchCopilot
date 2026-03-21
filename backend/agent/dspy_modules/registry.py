"""DSPy 编译模块注册表。应用启动时扫描 compiled_prompts/ 目录，按名称注册。"""

from pathlib import Path

from backend.core.logger import get_logger

logger = get_logger(__name__)

COMPILED_DIR = Path(__file__).parent.parent / "compiled_prompts"


class ModuleRegistry:
    """DSPy 编译模块注册表。

    注册 DSPy Module 时自动尝试从 compiled_prompts/ 加载编译产物。
    ``get()`` 返回 ``None`` 时调用方应回退到 YAML + with_structured_output 路径。
    """

    def __init__(self, compiled_dir: Path = COMPILED_DIR) -> None:
        self._modules: dict[str, object] = {}
        self._compiled_dir = compiled_dir

    def register(self, name: str, module: object) -> None:
        """注册模块。若 compiled_prompts/{name}.json 存在则自动加载编译产物。

        Args:
            name: 模块名称，如 ``"supervisor_routing"``。
            module: dspy.Module 实例。

        Raises:
            RuntimeError: 编译产物存在但加载失败时抛出，不静默忽略。
        """
        compiled_path = self._compiled_dir / f"{name}.json"
        if compiled_path.exists():
            try:
                module.load(str(compiled_path))  # type: ignore[union-attr]
                logger.info(
                    "dspy_module_loaded",
                    name=name,
                    path=str(compiled_path),
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load compiled DSPy module '{name}' from {compiled_path}: {exc}"
                ) from exc
        else:
            logger.info(
                "dspy_module_registered_no_compiled",
                name=name,
            )
        self._modules[name] = module

    def get(self, name: str) -> object | None:
        """按名称获取已注册模块。未注册返回 None。"""
        return self._modules.get(name)

    def has(self, name: str) -> bool:
        """检查模块是否已注册。"""
        return name in self._modules
