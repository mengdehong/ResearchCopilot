"""Event translator tests."""

from backend.services.event_translator import (
    translate_event,
    translate_stream,
    translate_to_run_event,
)


class TestTranslateEvent:
    def test_known_event(self) -> None:
        result = translate_event({"event": "events/metadata", "data": {"run_id": "r1"}})
        assert result is not None
        assert result["event"] == "metadata"
        assert result["data"]["run_id"] == "r1"

    def test_token_event(self) -> None:
        result = translate_event(
            {
                "event": "events/on_chat_model_stream",
                "data": {"chunk": "hello"},
            }
        )
        assert result is not None
        assert result["event"] == "token"

    def test_interrupt_event(self) -> None:
        result = translate_event({"event": "__interrupt__", "data": {"question": "?"}})
        assert result is not None
        assert result["event"] == "interrupt"

    def test_unknown_event_returns_none(self) -> None:
        result = translate_event({"event": "unknown/event", "data": {}})
        assert result is None

    def test_missing_event_key(self) -> None:
        result = translate_event({"data": {}})
        assert result is None


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

    def test_interrupt_confirm_execute_preserves_code(self) -> None:
        """confirm_execute interrupt 应保留 code 字段。"""
        result = translate_to_run_event(
            {
                "event": "__interrupt__",
                "data": {
                    "action": "confirm_execute",
                    "run_id": "r1",
                    "thread_id": "t1",
                    "code": "print('hello')",
                    "title": "Review Code",
                },
            }
        )
        assert result is not None
        assert result["data"]["code"] == "print('hello')"

    def test_interrupt_confirm_finalize_preserves_content(self) -> None:
        """confirm_finalize interrupt 应保留 content 字段。"""
        result = translate_to_run_event(
            {
                "event": "__interrupt__",
                "data": {
                    "action": "confirm_finalize",
                    "run_id": "r1",
                    "thread_id": "t1",
                    "content": "# Report\nSome content",
                },
            }
        )
        assert result is not None
        assert result["data"]["content"] == "# Report\nSome content"


class TestTranslateStream:
    async def test_filters_unknown_events(self) -> None:
        async def _raw_stream():
            yield {"event": "events/metadata", "data": {"id": "1"}}
            yield {"event": "unknown/event", "data": {}}
            yield {"event": "events/on_chat_model_stream", "data": {"chunk": "hi"}}
            yield {"event": "another_unknown", "data": {}}

        results = [e async for e in translate_stream(_raw_stream())]
        assert len(results) == 2
        assert results[0]["event"] == "metadata"
        assert results[1]["event"] == "token"

    async def test_empty_stream(self) -> None:
        async def _empty():
            return
            yield

        results = [e async for e in translate_stream(_empty())]
        assert len(results) == 0
