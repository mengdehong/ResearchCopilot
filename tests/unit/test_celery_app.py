"""Celery 应用配置单元测试。"""

import structlog


def test_celery_app_uses_settings_broker_url() -> None:
    """celery_app 应使用 Settings 中的 celery_broker_url。"""
    from backend.workers.celery_app import app

    # Settings 在 module-level 构造, 验证 config 已经设置
    assert app.conf.broker_url is not None
    assert app.conf.result_backend is not None


def test_celery_app_json_serializer() -> None:
    """Celery 应使用 JSON 序列化。"""
    from backend.workers.celery_app import app

    assert app.conf.task_serializer == "json"


def test_celery_app_acks_late() -> None:
    """任务失败可重试: acks_late = True。"""
    from backend.workers.celery_app import app

    assert app.conf.task_acks_late is True


def test_celery_app_prefetch_multiplier() -> None:
    """长任务不预取: prefetch_multiplier = 1。"""
    from backend.workers.celery_app import app

    assert app.conf.worker_prefetch_multiplier == 1


def test_trace_id_propagation_on_task_prerun() -> None:
    """task_prerun 信号应将 trace_id 绑定到 structlog contextvars。"""
    from backend.workers.celery_app import propagate_trace_id

    structlog.contextvars.clear_contextvars()
    kwargs = {"trace_id": "abc-123", "other": "value"}

    propagate_trace_id(sender=None, kwargs=kwargs)

    ctx = structlog.contextvars.get_contextvars()
    assert ctx["trace_id"] == "abc-123"
    # trace_id 应从 kwargs 中移除
    assert "trace_id" not in kwargs
    # 其他参数不受影响
    assert kwargs["other"] == "value"

    structlog.contextvars.clear_contextvars()


def test_trace_id_not_set_when_missing() -> None:
    """kwargs 中没有 trace_id 时, contextvars 不应被修改。"""
    from backend.workers.celery_app import propagate_trace_id

    structlog.contextvars.clear_contextvars()
    kwargs = {"other": "value"}

    propagate_trace_id(sender=None, kwargs=kwargs)

    ctx = structlog.contextvars.get_contextvars()
    assert "trace_id" not in ctx

    structlog.contextvars.clear_contextvars()


def test_clear_trace_id_on_task_postrun() -> None:
    """task_postrun 信号应清理 structlog contextvars。"""
    from backend.workers.celery_app import clear_trace_id

    structlog.contextvars.bind_contextvars(trace_id="abc-123")

    clear_trace_id(sender=None)

    ctx = structlog.contextvars.get_contextvars()
    assert "trace_id" not in ctx


def test_celery_app_time_limit() -> None:
    """task_time_limit 必须大于 0，防止 Worker 永久挂起。"""
    from backend.workers.celery_app import app

    assert app.conf.task_time_limit > 0
    assert app.conf.task_soft_time_limit > 0
    assert app.conf.task_soft_time_limit < app.conf.task_time_limit


def test_celery_app_result_expires() -> None:
    """result_expires 必须大于 0，防止 Redis 无限堆积。"""
    from backend.workers.celery_app import app

    assert app.conf.result_expires > 0


def test_celery_app_reject_on_worker_lost() -> None:
    """Worker 崩溃时应拒绝任务，确保死信队列追踪。"""
    from backend.workers.celery_app import app

    assert app.conf.task_reject_on_worker_lost is True


def test_celery_app_acks_on_failure_or_timeout() -> None:
    """失败或超时时不 ack，配合 acks_late 确保任务不丢失。"""
    from backend.workers.celery_app import app

    assert app.conf.task_acks_on_failure_or_timeout is False
