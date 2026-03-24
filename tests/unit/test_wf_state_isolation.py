"""WF State 隔离测试。验证各 subgraph input/output 只暴露 SharedState。"""

from unittest.mock import MagicMock

import pytest

from backend.agent.state import SharedState
from backend.agent.workflows import (
    build_critique_graph,
    build_discovery_graph,
    build_execution_graph,
    build_extraction_graph,
    build_ideation_graph,
    build_publish_graph,
)


def _shared_state_keys() -> set[str]:
    """提取 SharedState 及其基类 _SharedBase 的所有字段名。"""
    keys: set[str] = set()
    for cls in SharedState.__mro__:
        if hasattr(cls, "__annotations__"):
            keys.update(cls.__annotations__.keys())
    return keys


_BUILDERS = [
    ("discovery", build_discovery_graph, {"llm": MagicMock()}),
    (
        "extraction",
        build_extraction_graph,
        {"llm": MagicMock(), "rag_engine": MagicMock(), "session_factory": MagicMock()},
    ),
    ("ideation", build_ideation_graph, {"llm": MagicMock()}),
    ("execution", build_execution_graph, {"llm": MagicMock()}),
    ("critique", build_critique_graph, {"llm": MagicMock()}),
    ("publish", build_publish_graph, {"llm": MagicMock()}),
]


@pytest.mark.unit
@pytest.mark.parametrize("name,builder,kwargs", _BUILDERS, ids=[b[0] for b in _BUILDERS])
def test_subgraph_input_schema_equals_shared_state(
    name: str,
    builder,
    kwargs: dict,
) -> None:
    """各 WF subgraph input_schema 字段应严格等于 SharedState。"""
    graph = builder(**kwargs)
    input_keys = set(graph.input_schema.__annotations__.keys())
    expected = _shared_state_keys()
    assert input_keys == expected, f"{name} input_schema 泄漏字段: {input_keys - expected}"


@pytest.mark.unit
@pytest.mark.parametrize("name,builder,kwargs", _BUILDERS, ids=[b[0] for b in _BUILDERS])
def test_subgraph_output_schema_equals_shared_state(
    name: str,
    builder,
    kwargs: dict,
) -> None:
    """各 WF subgraph output_schema 字段应严格等于 SharedState。"""
    graph = builder(**kwargs)
    output_keys = set(graph.output_schema.__annotations__.keys())
    expected = _shared_state_keys()
    assert output_keys == expected, f"{name} output_schema 泄漏字段: {output_keys - expected}"
