"""
Repository 패키지

데이터 접근 계층을 담당하는 Repository 클래스들을 정의합니다.
Repository 패턴을 통해 데이터베이스 접근 로직을 캡슐화합니다.
"""

from .chat_repository import ChatRepository

__all__ = ["ChatRepository"] 
