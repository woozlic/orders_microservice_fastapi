from celery import Celery
from .settings import settings

celery = Celery(
    "app",
    broker=settings.redis_url,
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/1",
)
celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    timezone="UTC",
)

@celery.task(name="ping")
def ping() -> str:
    return "pong"