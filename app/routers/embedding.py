from fastapi import APIRouter
from app.schemas.embed_request import EmbedRequest
from app.tasks.embedding_task import embed_bookmark
from app.tasks.similarity_task import calculate_similarity
from celery import chain

router = APIRouter()

@router.post("/embed")
def embed_bookmark_api(request: EmbedRequest):
    """
    북마크 임베딩 후 유사도 검사까지 순차 실행
    """
    workflow = chain(
        embed_bookmark.s(request.id, request.user_id, request.s3_key),
        calculate_similarity.s()
    )

    result = workflow.apply_async()

    return {
        "status": "started",
        "task_id": result.id  
    }
