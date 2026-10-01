"""Celery-приложение. Используется только для фоновых задач, не как event-bus."""
from celery import Celery

from .settings import settings

celery = Celery(
    "orders_microservice_fastapi",
    broker=settings.redis_url,
    backend=settings.celery_backend_url,
)
celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    timezone="UTC",
)

from . import tasks  # noqa: E402,F401  (регистрация задач)
