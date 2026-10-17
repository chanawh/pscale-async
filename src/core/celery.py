import os

from celery import Celery

from src.core.config import settings

# Create Celery app
celery_app = Celery(
    "log_intelligence",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.workers.log_processor"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Windows compatibility: use eager mode for local development
    task_always_eager=os.environ.get("CELERY_EAGER", "true").lower() == "true",
    task_eager_propagates=True,
    task_store_eager_result=True,
    # Redis result backend configuration
    result_backend=settings.celery_result_backend,
    broker_connection_retry_on_startup=True,
)
