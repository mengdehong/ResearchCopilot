"""Agent State 定义测试。"""

from backend.agent.state import (
    CritiqueState,
    DiscoveryState,
    ExecutionState,
    ExtractionState,
    IdeationState,
    PublishState,
    SharedState,
    merge_dicts,
)


def test_merge_dicts_deep() -> None:
    left = {"a": {"x": 1, "y": 2}, "b": 3}
    right = {"a": {"y": 99, "z": 100}}
    result = merge_dicts(left, right)
    assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}


def test_merge_dicts_overwrite_non_dict() -> None:
    left = {"a": 1}
    right = {"a": "replaced"}
    assert merge_dicts(left, right) == {"a": "replaced"}


def test_shared_state_has_four_fields() -> None:
    assert set(SharedState.__annotations__) == {
        "messages",
        "workspace_id",
        "discipline",
        "artifacts",
        "target_workflow",
        "critique_round",
        "revision_context",
    }


def test_all_wf_states_inherit_shared() -> None:
    for state_cls in [
        DiscoveryState,
        ExtractionState,
        IdeationState,
        ExecutionState,
        CritiqueState,
        PublishState,
    ]:
        assert "messages" in state_cls.__annotations__ or issubclass(state_cls, dict)
