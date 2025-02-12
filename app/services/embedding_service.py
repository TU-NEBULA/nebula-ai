from app.core.embedding_model import get_embedding
from app.models.graph_schemas import DocumentCreate

def generate_embedding(html_text: str):
    """HTML 입력을 임베딩 벡터로 변환"""
    embedding = get_embedding(html_text)  

    if isinstance(embedding, list) and isinstance(embedding[0], list):
        embedding = embedding[0] 

    document = DocumentCreate(doc_id="asdf", text=html_text, embedding=embedding)
    return document
