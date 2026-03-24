"""ModuleRegistry 单元测试。"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agent.dspy_modules.registry import ModuleRegistry


def _make_mock_module() -> MagicMock:
    """创建遵循 dspy.Module 接口的 mock 对象。"""
    module = MagicMock()
    module.load = MagicMock()
    return module


# ── 注册与获取 ──


def test_register_and_get_returns_module() -> None:
    """注册后 get() 能返回已注册的 module。"""
    registry = ModuleRegistry(compiled_dir=Path("/nonexistent"))
    module = _make_mock_module()
    registry.register("test_module", module)
    assert registry.get("test_module") is module


def test_get_unregistered_returns_none() -> None:
    """get() 未注册的名称返回 None。"""
    registry = ModuleRegistry(compiled_dir=Path("/nonexistent"))
    assert registry.get("missing") is None


def test_has_returns_true_for_registered() -> None:
    """has() 已注册的名称返回 True。"""
    registry = ModuleRegistry(compiled_dir=Path("/nonexistent"))
    module = _make_mock_module()
    registry.register("test_module", module)
    assert registry.has("test_module") is True


def test_has_returns_false_for_unregistered() -> None:
    """has() 未注册的名称返回 False。"""
    registry = ModuleRegistry(compiled_dir=Path("/nonexistent"))
    assert registry.has("missing") is False


# ── 编译产物加载 ──


def test_register_loads_compiled_json(tmp_path: Path) -> None:
    """compiled_prompts/ 中存在合法 JSON 时，register() 应调用 module.load()。"""
    compiled_path = tmp_path / "my_module.json"
    compiled_path.write_text(json.dumps({"optimized": True}))

    registry = ModuleRegistry(compiled_dir=tmp_path)
    module = _make_mock_module()
    registry.register("my_module", module)

    module.load.assert_called_once_with(str(compiled_path))
    assert registry.get("my_module") is module


def test_register_without_compiled_json_skips_load(tmp_path: Path) -> None:
    """compiled_prompts/ 为空时，register() 不调用 module.load()。"""
    registry = ModuleRegistry(compiled_dir=tmp_path)
    module = _make_mock_module()
    registry.register("missing_module", module)

    module.load.assert_not_called()
    assert registry.get("missing_module") is module


def test_register_corrupt_json_raises_runtime_error(tmp_path: Path) -> None:
    """编译产物损坏时，register() 抛出 RuntimeError，不静默失败。"""
    compiled_path = tmp_path / "bad_module.json"
    compiled_path.write_text("{corrupt JSON!!!")

    registry = ModuleRegistry(compiled_dir=tmp_path)
    module = _make_mock_module()
    module.load.side_effect = ValueError("Invalid JSON")

    with pytest.raises(RuntimeError, match="Failed to load compiled DSPy module"):
        registry.register("bad_module", module)
