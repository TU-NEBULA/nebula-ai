from fastapi import APIRouter
from celery.result import AsyncResult
from app.core.celery_worker import celery
from app.schemas.embed_status_response import EmbedStatusResponse

router = APIRouter()

@router.get("/embed/status/{task_id}", response_model=EmbedStatusResponse)
def get_embed_status(task_id: str):
    result = AsyncResult(task_id, app=celery)

    return EmbedStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result
    )
