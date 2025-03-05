from fastapi import APIRouter
from datetime import datetime
from app.schemas.embed_response import EmbedResponse
from app.schemas.embed_request import EmbedRequest
from app.tasks.embedding_task import embed_bookmark

router = APIRouter()

@router.post("/embed", response_model=EmbedResponse)
def embeddging(request: EmbedRequest):
    """북마크 임베딩 작업을 Celery로 비동기 트리거"""
    
    task = embed_bookmark.delay(
        bookmark_id=request.id,
        user_id=request.user_id,
        s3_key=request.s3_key
    )

    return EmbedResponse(
        id=request.id,
        status="queued",
        message="임베딩 작업이 Celery에 등록되었습니다.",
        task_id=task.id
    )
