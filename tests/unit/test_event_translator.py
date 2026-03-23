"""Event translator tests — uses current translate_to_run_event API."""

from backend.services.event_translator import translate_to_run_event


class TestTranslateToRunEvent:
    def test_interrupt_passes_candidates_as_papers(self) -> None:
        """interrupt 事件应将 candidates 字段传递为 papers。"""
        candidates = [
            {"id": "p1", "title": "Paper 1"},
            {"id": "p2", "title": "Paper 2"},
        ]
        result = translate_to_run_event(
            {
                "event": "__interrupt__",
                "data": {
                    "action": "select_papers",
                    "run_id": "r1",
                    "thread_id": "t1",
                    "candidates": candidates,
                },
            }
        )
        assert result is not None
        assert result["event_type"] == "interrupt"
        assert result["data"]["action"] == "select_papers"
        assert result["data"]["papers"] == candidates

    def test_interrupt_without_candidates(self) -> None:
        """无 candidates 时 papers 应为空列表。"""
        result = translate_to_run_event(
            {
                "event": "__interrupt__",
                "data": {"action": "confirm_execute", "run_id": "r1"},
            }
        )
        assert result is not None
        assert result["data"]["papers"] == []

    def test_unknown_event_returns_none(self) -> None:
        result = translate_to_run_event({"event": "unknown/event", "data": {}})
        assert result is None

    def test_missing_event_key_returns_none(self) -> None:
        result = translate_to_run_event({"data": {}})
        assert result is None

    def test_node_start_event(self) -> None:
        result = translate_to_run_event(
            {
                "event": "on_chain_start",
                "name": "discovery",
                "data": {"name": "discovery", "run_id": "r1"},
                "metadata": {"langgraph_node": "discovery"},
            }
        )
        assert result is not None
        assert result["event_type"] == "node_start"

    def test_node_end_event(self) -> None:
        result = translate_to_run_event(
            {
                "event": "on_chain_end",
                "name": "extraction",
                "data": {"name": "extraction", "run_id": "r1"},
                "metadata": {"langgraph_node": "extraction"},
            }
        )
        assert result is not None
        assert result["event_type"] == "node_end"

    def test_event_without_langgraph_node_is_filtered(self) -> None:
        """node_start/end without langgraph_node in metadata should be dropped."""
        result = translate_to_run_event(
            {
                "event": "on_chain_start",
                "name": "some_internal_chain",
                "data": {},
                "metadata": {},
            }
        )
        assert result is None
