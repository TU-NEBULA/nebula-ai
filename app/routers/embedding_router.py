from fastapi import APIRouter, Form
from app.services.embedding_service import generate_embedding
from app.services.neo4j_service import get_html_url_from_star
from app.models.graph_schemas import DocumentCreate
from typing import List

router = APIRouter()

@router.post("/embed/", response_model=DocumentCreate)
def embed_text(html: str = Form(...)):
    """HTML 문자열을 입력받아 임베딩 변환"""
    return generate_embedding(html)


@router.post("/embed/{id}")
def embed_text(id: str):
    """Neo4j에 저장된 HTML 문자열을 입력받아 임베딩 변환"""

    print(f"ID: {id}")
    html = get_html_url_from_star(id)
    return html
