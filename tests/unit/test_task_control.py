"""Agent task control — TDD tests for pause/kill API.

Tests pause_run, unpause_run, kill_run in agent_service and langgraph_runner.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.thread import Thread
from backend.models.workspace import Workspace


def _user():
    from backend.models.user import User

    u = User()
    u.id = uuid.uuid4()
    u.external_id = "ext"
    u.email = "a@b.com"
    u.display_name = "Test"
    u.settings = {}
    u.created_at = u.updated_at = datetime.now(tz=UTC)
    return u


def _ws(owner_id: uuid.UUID) -> Workspace:
    ws = Workspace()
    ws.id = uuid.uuid4()
    ws.owner_id = owner_id
    ws.name = "WS"
    ws.discipline = "cs"
    ws.is_deleted = False
    ws.created_at = ws.updated_at = datetime.now(tz=UTC)
    return ws


def _thread(ws_id: uuid.UUID) -> Thread:
    t = Thread()
    t.id = uuid.uuid4()
    t.workspace_id = ws_id
    t.title = "Thread"
    t.status = "running"
    t.created_at = t.updated_at = datetime.now(tz=UTC)
    return t


# ---------------------------------------------------------------------------
# LangGraphRunner pause/unpause
# ---------------------------------------------------------------------------


class TestRunnerPauseUnpause:
    """Test that LangGraphRunner supports pausing and unpausing runs."""

    async def test_pause_run_sets_paused_state(self) -> None:
        from backend.clients.langgraph_runner import LangGraphRunner

        graph = MagicMock()
        runner = LangGraphRunner(graph)

        # Manually add a run handle
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(asyncio.sleep(100))
        from backend.clients.langgraph_runner import RunHandle

        handle = RunHandle(task=task, queue=queue, thread_id="t1")
        runner._active_runs["run-1"] = handle

        await runner.pause_run("run-1")
        assert handle.paused is True

        task.cancel()

    async def test_unpause_run_clears_paused_state(self) -> None:
        from backend.clients.langgraph_runner import LangGraphRunner

        graph = MagicMock()
        runner = LangGraphRunner(graph)

        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(asyncio.sleep(100))
        from backend.clients.langgraph_runner import RunHandle

        handle = RunHandle(task=task, queue=queue, thread_id="t1")
        handle.paused = True
        runner._active_runs["run-1"] = handle

        await runner.unpause_run("run-1")
        assert handle.paused is False

        task.cancel()

    async def test_pause_nonexistent_run_is_noop(self) -> None:
        from backend.clients.langgraph_runner import LangGraphRunner

        graph = MagicMock()
        runner = LangGraphRunner(graph)
        # Should not raise
        await runner.pause_run("nonexistent")


# ---------------------------------------------------------------------------
# agent_service pause/kill
# ---------------------------------------------------------------------------


class TestAgentServicePauseKill:
    """Test agent_service.pause_run and kill_run functions."""

    @patch("backend.services.agent_service.run_snapshot_repo")
    @patch("backend.services.agent_service.base_repo")
    async def test_pause_run_success(self, mock_base: MagicMock, mock_snap_repo: MagicMock) -> None:
        from backend.services.agent_service import pause_run

        session = AsyncMock()
        owner = _user()
        ws = _ws(owner.id)
        thread = _thread(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws, thread])

        snap = MagicMock()
        snap.status = "running"
        mock_snap_repo.get_by_run_id = AsyncMock(return_value=snap)

        runner = MagicMock()
        runner.pause_run = AsyncMock()

        run_id = str(uuid.uuid4())
        result = await pause_run(
            session,
            runner,
            thread_id=thread.id,
            run_id=run_id,
            owner=owner,
        )
        assert result is True
        runner.pause_run.assert_awaited_once_with(run_id)
        assert snap.status == "paused"

    @patch("backend.services.agent_service.run_snapshot_repo")
    @patch("backend.services.agent_service.base_repo")
    async def test_kill_run_sets_killed_status(
        self, mock_base: MagicMock, mock_snap_repo: MagicMock
    ) -> None:
        from backend.services.agent_service import kill_run

        session = AsyncMock()
        owner = _user()
        ws = _ws(owner.id)
        thread = _thread(ws.id)
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws, thread])

        snap = MagicMock()
        snap.status = "running"
        mock_snap_repo.get_by_run_id = AsyncMock(return_value=snap)

        runner = MagicMock()
        runner.cancel_run = AsyncMock()

        run_id = str(uuid.uuid4())
        result = await kill_run(
            session,
            runner,
            thread_id=thread.id,
            run_id=run_id,
            owner=owner,
        )
        assert result is True
        runner.cancel_run.assert_awaited_once_with(run_id)
        assert snap.status == "killed"

    @patch("backend.services.agent_service.base_repo")
    async def test_pause_run_forbidden(self, mock_base: MagicMock) -> None:
        from backend.services.agent_service import pause_run

        session = AsyncMock()
        owner = _user()
        thread = _thread(uuid.uuid4())
        ws = _ws(uuid.uuid4())
        mock_base.get_by_id = AsyncMock(side_effect=[thread, ws])

        runner = MagicMock()
        result = await pause_run(
            session, runner, thread_id=thread.id, run_id=str(uuid.uuid4()), owner=owner
        )
        assert result is False
