from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "aimv",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.include = ["app.workers.generation_tasks"]
