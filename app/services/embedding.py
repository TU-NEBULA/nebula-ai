from app.core.embedding_model import get_embedding
from app.external.s3_service import download_html_from_s3

def generate_embedding_from_s3(id: str, s3_key: str):
    """s3 키를 입력받아 HTML 문자열 임베딩 변환"""

    html_content = download_html_from_s3(s3_key)
    embedding = get_embedding(html_content)

    return embedding
