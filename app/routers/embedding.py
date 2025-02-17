from fastapi import APIRouter
from app.services.embedding import generate_embedding_from_s3
from app.schemas.embed_response import EmbedResponse
from app.schemas.embed_request import EmbedRequest

router = APIRouter()

@router.post("/embed", response_model=EmbedResponse)
def embeddging(request: EmbedRequest):
    """Neo4j id와 S3 키를 입력받아 S3에 있는 HTML 문자열 임베딩 변환"""
    html_content = """ """
    
    embeddging_res = generate_embedding_from_s3(request.id, html_content)

    return EmbedResponse(
        id=request.id,
        s3_key=request.s3_key,
        embeddings=embeddging_res
    )
