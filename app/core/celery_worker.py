from celery import Celery
from app.core.config import settings

celery = Celery(
    "nebula",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL
)

celery.conf.task_routes = {
    "tasks.save_bookmark.*": {"queue": "bookmark_save"},
}

celery.autodiscover_tasks(['app.tasks'])
from app.tasks import bookmark_save_task
