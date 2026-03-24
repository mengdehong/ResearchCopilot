"""E2E 测试共享 fixtures。

基于进程内 FastAPI app + ASGITransport 的端到端 API 测试。
运行前需确保 `make infra` 已启动 PostgreSQL/Redis/MinIO。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy import delete

from backend.api.dependencies import get_lg_runner
from backend.api.routers import agent, auth, document, editor, health, workspace
from backend.api.routers.document import _get_storage
from backend.clients.storage_client import StorageClient
from backend.core.config import Settings
from backend.core.database import create_engine, create_session_factory
from backend.core.exceptions import AppError, app_error_handler
from backend.models.user import User
from backend.models.workspace import Workspace

from .mocks.mock_langgraph import MockLangGraphRunner
from .seed import SeedData, sign_test_token

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# ---------------------------------------------------------------------------
# 所有 E2E 测试和 fixtures 使用 session 级 event loop
# ---------------------------------------------------------------------------


# asyncio_default_test_loop_scope / asyncio_default_fixture_loop_scope
# 在 pyproject.toml 中设置为 "session"，确保所有 async 测试共享一个 event loop。


# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

_mock_lg_runner = MockLangGraphRunner()
_mock_storage = StorageClient(base_dir="/tmp/research-copilot-e2e-uploads")


def _create_test_app() -> FastAPI:
    """创建不含 BaseHTTPMiddleware 的测试 app。"""
    test_app = FastAPI(
        title="Research Copilot (E2E Test)",
        version="0.1.0-test",
    )
    test_app.add_exception_handler(AppError, app_error_handler)
    test_app.include_router(health.router)
    test_app.include_router(auth.router)
    test_app.include_router(workspace.router)
    test_app.include_router(document.router)
    test_app.include_router(editor.router)
    test_app.include_router(agent.router)
    test_app.dependency_overrides[get_lg_runner] = lambda: _mock_lg_runner
    test_app.dependency_overrides[_get_storage] = lambda: _mock_storage
    return test_app


_test_app = _create_test_app()


@pytest.fixture(scope="session")
def mock_lg_runner() -> MockLangGraphRunner:
    return _mock_lg_runner


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_app() -> AsyncGenerator[None, None]:
    """初始化 test_app.state。"""
    settings = Settings()
    engine = create_engine(settings.database_url, echo=False)
    session_factory = create_session_factory(engine)
    _test_app.state.settings = settings
    _test_app.state.session_factory = session_factory
    yield
    _test_app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Session 级 httpx 异步客户端。"""
    transport = ASGITransport(app=_test_app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=httpx.Timeout(30.0),
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def seed_data(
    test_client: httpx.AsyncClient,
) -> AsyncGenerator[SeedData, None]:
    """创建种子数据。"""
    settings = _test_app.state.settings
    factory = _test_app.state.session_factory

    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    token_a = sign_test_token(user_a_id, settings.jwt_secret, settings.jwt_algorithm)
    token_b = sign_test_token(user_b_id, settings.jwt_secret, settings.jwt_algorithm)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 清理之前可能残留的 e2e 数据（使 fixture 幂等）
    async with factory() as session:
        from sqlalchemy import select

        from backend.models.document import Document
        from backend.models.editor_draft import EditorDraft
        from backend.models.run_snapshot import RunSnapshot
        from backend.models.thread import Thread

        old_user_ids_result = await session.execute(
            select(User.id).where(User.external_id.like("e2e-test:%"))
        )
        old_user_ids = [row[0] for row in old_user_ids_result.all()]
        if old_user_ids:
            old_ws_ids_result = await session.execute(
                select(Workspace.id).where(Workspace.owner_id.in_(old_user_ids))
            )
            old_ws_ids = [row[0] for row in old_ws_ids_result.all()]
            if old_ws_ids:
                old_thread_ids_result = await session.execute(
                    select(Thread.id).where(Thread.workspace_id.in_(old_ws_ids))
                )
                old_thread_ids = [row[0] for row in old_thread_ids_result.all()]
                if old_thread_ids:
                    await session.execute(
                        delete(EditorDraft).where(EditorDraft.thread_id.in_(old_thread_ids))
                    )
                    await session.execute(
                        delete(RunSnapshot).where(RunSnapshot.thread_id.in_(old_thread_ids))
                    )
                    await session.execute(delete(Thread).where(Thread.id.in_(old_thread_ids)))
                await session.execute(delete(Document).where(Document.workspace_id.in_(old_ws_ids)))
                await session.execute(delete(Workspace).where(Workspace.id.in_(old_ws_ids)))
            await session.execute(delete(User).where(User.id.in_(old_user_ids)))
            await session.commit()

    # 创建新用户
    async with factory() as session:
        session.add(
            User(
                id=user_a_id,
                external_id="e2e-test:user-a",
                email="e2e-user-a@test.local",
                display_name="E2E User A",
                settings={},
            )
        )
        session.add(
            User(
                id=user_b_id,
                external_id="e2e-test:user-b",
                email="e2e-user-b@test.local",
                display_name="E2E User B",
                settings={},
            )
        )
        await session.commit()

    ws_a = await test_client.post(
        "/api/v1/workspaces",
        headers=headers_a,
        json={"name": "E2E Test Workspace", "discipline": "computer_science"},
    )
    assert ws_a.status_code == 201, f"seed ws_a: {ws_a.text}"
    ws_b = await test_client.post(
        "/api/v1/workspaces",
        headers=headers_b,
        json={"name": "E2E User B Workspace", "discipline": "biology"},
    )
    assert ws_b.status_code == 201, f"seed ws_b: {ws_b.text}"

    yield SeedData(
        user_id=user_a_id,
        user_email="e2e-user-a@test.local",
        access_token=token_a,
        user_b_id=user_b_id,
        user_b_email="e2e-user-b@test.local",
        user_b_access_token=token_b,
        workspace_id=uuid.UUID(ws_a.json()["id"]),
        workspace_b_id=uuid.UUID(ws_b.json()["id"]),
    )

    async with factory() as session:
        from backend.models.document import Document
        from backend.models.editor_draft import EditorDraft
        from backend.models.run_snapshot import RunSnapshot
        from backend.models.thread import Thread

        user_ids = [user_a_id, user_b_id]

        # 查找相关 workspace IDs
        from sqlalchemy import select

        ws_ids_result = await session.execute(
            select(Workspace.id).where(Workspace.owner_id.in_(user_ids))
        )
        ws_ids = [row[0] for row in ws_ids_result.all()]

        if ws_ids:
            # 查找相关 thread IDs
            thread_ids_result = await session.execute(
                select(Thread.id).where(Thread.workspace_id.in_(ws_ids))
            )
            thread_ids = [row[0] for row in thread_ids_result.all()]

            if thread_ids:
                await session.execute(
                    delete(EditorDraft).where(EditorDraft.thread_id.in_(thread_ids))
                )
                await session.execute(
                    delete(RunSnapshot).where(RunSnapshot.thread_id.in_(thread_ids))
                )
                await session.execute(delete(Thread).where(Thread.id.in_(thread_ids)))

            await session.execute(delete(Document).where(Document.workspace_id.in_(ws_ids)))
            await session.execute(delete(Workspace).where(Workspace.id.in_(ws_ids)))

        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.fixture(scope="session")
def auth_headers(seed_data: SeedData) -> dict[str, str]:
    return {"Authorization": f"Bearer {seed_data.access_token}"}


@pytest.fixture(scope="session")
def auth_headers_b(seed_data: SeedData) -> dict[str, str]:
    return {"Authorization": f"Bearer {seed_data.user_b_access_token}"}
