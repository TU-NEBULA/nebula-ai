from app.core.embedding_model import get_embedding

def generate_embedding_from_s3(html_text: str):
    """s3 키를 입력받아 HTML 문자열 임베딩 변환"""
    
