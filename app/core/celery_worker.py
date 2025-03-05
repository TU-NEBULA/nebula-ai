from celery import Celery
from app.core.config import settings

celery = Celery(
    "nebula",
    broker=f"amqp://{settings.RABBITMQ_HOST}//",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)

celery.conf.task_routes = {
    "app.tasks.embedding_task.*": {"queue": "embedding"},
}

celery.autodiscover_tasks(['app.tasks'])
from app.tasks import embedding_task
