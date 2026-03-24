"""Workers 模块。导出 Celery app 实例。"""

from backend.workers.celery_app import app as celery_app

__all__ = ["celery_app"]
