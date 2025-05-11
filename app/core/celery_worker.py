from celery import Celery
from app.core.config import settings

celery = Celery(
    "nebula",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL
    # backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)

celery.conf.task_routes = {
    "app.tasks.similarity_task.*": {"queue": "embedding"},
    "tasks.save_bookmark.*": {"queue": "bookmark_save"},
}

celery.autodiscover_tasks(['app.tasks'])
from app.tasks import similarity_task
from app.tasks import bookmark_save_task
