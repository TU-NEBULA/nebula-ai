"""
OpenAI 클라이언트 유틸리티 모듈

이 모듈은 OpenAI API 클라이언트를 캐시하고 관리하는 유틸리티 함수들을 정의합니다.

주요 기능:
- OpenAI API 클라이언트 초기화
- 캐시된 클라이언트 인스턴스 반환
"""
from functools import lru_cache
from openai import AsyncOpenAI

from app.core.config import settings

@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """OpenAI API 클라이언트 반환 함수"""
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
