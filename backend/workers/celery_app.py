"""Celery 实例配置。Redis broker + rpc 结果后端, trace_id 信号传播。"""

import structlog
from celery import Celery
from celery.signals import task_postrun, task_prerun

from backend.core.config import Settings

settings = Settings()

app = Celery("research_copilot")
app.config_from_object(
    {
        "broker_url": settings.celery_broker_url,
        "result_backend": settings.celery_result_backend,
        "task_serializer": "json",
        "task_track_started": True,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        # 防止 Worker 永久挂起
        "task_time_limit": settings.celery_task_time_limit,
        "task_soft_time_limit": settings.celery_task_soft_time_limit,
        # 防止 Redis 任务结果无限堆积
        "result_expires": settings.celery_result_expires,
        # Worker 崩溃时拒绝任务（死信队列追踪）
        "task_reject_on_worker_lost": True,
        # 超时/失败时不 ack，配合 acks_late 确保任务不丢失
        "task_acks_on_failure_or_timeout": False,
        "include": ["backend.workers.tasks.ingest_document"],
    }
)


@task_prerun.connect
def propagate_trace_id(sender: object, kwargs: dict[str, object], **_: object) -> None:
    """从 kwargs 恢复 trace_id 到 structlog contextvars。"""
    trace_id = kwargs.pop("trace_id", None)
    if trace_id:
        structlog.contextvars.bind_contextvars(trace_id=trace_id)


@task_postrun.connect
def clear_trace_id(sender: object, **_: object) -> None:
    """任务结束后清理 contextvars。"""
    structlog.contextvars.clear_contextvars()
