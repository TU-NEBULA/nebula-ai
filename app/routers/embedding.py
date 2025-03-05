from fastapi import APIRouter
from app.schemas.embed_response import EmbedResponse
from app.schemas.embed_request import EmbedRequest
from app.services.mq_publisher import publish_message

router = APIRouter()

@router.post("/embed", response_model=EmbedResponse)
def embeddging(request: EmbedRequest):
    """Neo4j id와 S3 키를 입력받아 RabbitMQ에 임베딩 작업 트리거"""

    # RabbitMQ에 메시지 발행
    message = {
        "id": request.id,
        "user_id": request.user_id,
        "s3_key": request.s3_key
    }
    publish_message(message)

    return EmbedResponse(
        id=request.id,
        status="queued",
        message="임베딩 작업이 큐에 등록되었습니다."
    )
