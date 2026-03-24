"""单元测试：backend.core.metrics + quota_service 中的 Prometheus metrics 联动。

使用独立 CollectorRegistry 避免全局注册表污染导致重复注册报错。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry, Counter

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_counter(registry: CollectorRegistry, name: str, labelnames: list[str]) -> Counter:
    """在指定 registry 中创建 Counter，用于测试隔离。"""
    return Counter(
        name=name,
        documentation="test",
        labelnames=labelnames,
        registry=registry,
    )


# ---------------------------------------------------------------------------
# tests for backend.core.metrics module structure
# ---------------------------------------------------------------------------


def test_metrics_module_exports_expected_counters() -> None:
    """metrics.py 应暴露 llm_tokens_total 和 llm_requests_total 两个 Counter。"""
    from prometheus_client import Counter as PrometheusCounter

    from backend.core.metrics import llm_requests_total, llm_tokens_total

    assert isinstance(llm_tokens_total, PrometheusCounter)
    assert isinstance(llm_requests_total, PrometheusCounter)


def test_llm_tokens_total_has_correct_labels() -> None:
    """llm_tokens_total 应包含 model / workspace_id / token_type 三个 label。"""
    from backend.core.metrics import llm_tokens_total

    labels = llm_tokens_total._labelnames  # type: ignore[attr-defined]
    assert set(labels) == {"model", "workspace_id", "token_type"}


def test_llm_requests_total_has_correct_labels() -> None:
    """llm_requests_total 应包含 model / workspace_id / status 三个 label。"""
    from backend.core.metrics import llm_requests_total

    labels = llm_requests_total._labelnames  # type: ignore[attr-defined]
    assert set(labels) == {"model", "workspace_id", "status"}


# ---------------------------------------------------------------------------
# tests for quota_service metrics integration (isolated registry)
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_metrics() -> tuple[Counter, Counter]:
    """创建测试隔离的 Counter 对象（独立 registry）并 patch 到 quota_service 模块。"""
    registry = CollectorRegistry()
    tokens = _make_counter(
        registry, "llm_tokens_total_test", ["model", "workspace_id", "token_type"]
    )
    requests = _make_counter(
        registry, "llm_requests_total_test", ["model", "workspace_id", "status"]
    )
    return tokens, requests


@pytest.mark.asyncio
async def test_check_and_consume_increments_token_counter(
    isolated_metrics: tuple[Counter, Counter],
) -> None:
    """成功调用 check_and_consume 后，input/output token Counter 应分别递增。"""
    tokens_counter, requests_counter = isolated_metrics
    ws_id = uuid.uuid4()
    run_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("backend.services.quota_service.llm_tokens_total", tokens_counter),
        patch("backend.services.quota_service.llm_requests_total", requests_counter),
        patch(
            "backend.services.quota_service.get_quota_status",
            new=AsyncMock(return_value=MagicMock(remaining_tokens=999_999)),
        ),
    ):
        from backend.services.quota_service import check_and_consume

        await check_and_consume(
            mock_session,
            workspace_id=ws_id,
            run_id=run_id,
            input_tokens=100,
            output_tokens=50,
            model_name="gpt-4o",
        )

    ws_label = str(ws_id)
    assert (
        tokens_counter.labels(
            model="gpt-4o", workspace_id=ws_label, token_type="input"
        )._value.get()
        == 100
    )
    assert (
        tokens_counter.labels(
            model="gpt-4o", workspace_id=ws_label, token_type="output"
        )._value.get()
        == 50
    )
    assert (
        requests_counter.labels(model="gpt-4o", workspace_id=ws_label, status="ok")._value.get()
        == 1
    )


@pytest.mark.asyncio
async def test_quota_exceeded_increments_error_counter(
    isolated_metrics: tuple[Counter, Counter],
) -> None:
    """超额时 check_and_consume 应在 raise 前递增 quota_exceeded counter。"""
    from backend.core.exceptions import QuotaExceededError

    tokens_counter, requests_counter = isolated_metrics
    ws_id = uuid.uuid4()
    run_id = uuid.uuid4()

    mock_session = AsyncMock()

    with (
        patch("backend.services.quota_service.llm_tokens_total", tokens_counter),
        patch("backend.services.quota_service.llm_requests_total", requests_counter),
        patch(
            "backend.services.quota_service.get_quota_status",
            new=AsyncMock(return_value=MagicMock(remaining_tokens=10)),
        ),
    ):
        from backend.services.quota_service import check_and_consume

        with pytest.raises(QuotaExceededError):
            await check_and_consume(
                mock_session,
                workspace_id=ws_id,
                run_id=run_id,
                input_tokens=100,
                output_tokens=50,
                model_name="gpt-4o",
            )

    ws_label = str(ws_id)
    assert (
        requests_counter.labels(
            model="gpt-4o", workspace_id=ws_label, status="quota_exceeded"
        )._value.get()
        == 1
    )
    # token counter 不应递增
    assert (
        tokens_counter.labels(
            model="gpt-4o", workspace_id=ws_label, token_type="input"
        )._value.get()
        == 0
    )
