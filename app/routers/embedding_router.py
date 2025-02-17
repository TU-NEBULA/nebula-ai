from fastapi import APIRouter
from app.services.embedding_service import generate_embedding_from_s3
from app.schemas.embed_response import EmbedResponse
from app.schemas.embed_request import EmbedRequest

router = APIRouter()

@router.post("/embed", response_model=EmbedResponse)
def embed_text(request: EmbedRequest):
    """Neo4j id와 S3 키를 입력받아 S3에 있는 HTML 문자열 임베딩 변환"""

    

    return generate_embedding_from_s3(request)