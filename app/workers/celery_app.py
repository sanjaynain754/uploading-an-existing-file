from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "tasking_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # one task at a time per worker
    result_expires=86400,           # 24h
)
