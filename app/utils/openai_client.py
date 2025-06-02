"""
OpenAI 클라이언트 모듈

이 모듈은 OpenAI API와의 통신을 담당합니다.
"""

from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def get_openai_client():
    """
    OpenAI 클라이언트 인스턴스를 반환합니다.
    
    Returns:
        OpenAI: OpenAI 클라이언트 인스턴스
    """
    return client
