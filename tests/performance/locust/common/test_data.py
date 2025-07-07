"""
공통 테스트 데이터 모듈
HTTP와 RMQ 테스트에서 공유하는 데이터를 정의합니다.
"""

import random
import uuid
from typing import List, Dict, Any

# 사용자 ID 범위
USER_ID_RANGE = (1, 1000)

# 채팅 메시지 템플릿
CHAT_MESSAGES = [
    "안녕하세요! AI 추천 시스템에 대해 알려주세요.",
    "북마크 기능은 어떻게 작동하나요?",
    "머신러닝에 대한 좋은 자료를 추천해주세요.",
    "Python 웹 개발 관련 북마크를 찾고 있어요.",
    "FastAPI와 Django 중 어떤 것을 선택해야 할까요?",
    "데이터 사이언스 학습 로드맵을 알려주세요.",
    "클라우드 서비스 비교 자료가 있나요?",
    "개발자를 위한 유용한 도구들을 추천해주세요.",
]

# 테스트용 URL 목록
TEST_URLS = [
    "https://docs.python.org/3/",
    "https://fastapi.tiangolo.com/",
    "https://pytorch.org/tutorials/",
    "https://scikit-learn.org/stable/",
    "https://pandas.pydata.org/docs/",
    "https://numpy.org/doc/stable/",
    "https://matplotlib.org/stable/",
    "https://jupyter.org/documentation",
    "https://github.com/microsoft/vscode",
    "https://kubernetes.io/docs/",
    "https://react.dev/",
    "https://nextjs.org/docs",
    "https://tailwindcss.com/docs",
    "https://www.postgresql.org/docs/",
    "https://redis.io/documentation",
]

# 테스트용 제목 목록
TEST_TITLES = [
    "Python 공식 문서",
    "FastAPI 튜토리얼",
    "PyTorch 학습 가이드",
    "Scikit-learn 머신러닝",
    "Pandas 데이터 분석",
    "NumPy 수치 계산",
    "Matplotlib 시각화",
    "Jupyter 노트북 가이드",
    "VS Code 개발 도구",
    "Kubernetes 컨테이너 오케스트레이션",
    "React 공식 문서",
    "Next.js 프레임워크",
    "Tailwind CSS 스타일링",
    "PostgreSQL 데이터베이스",
    "Redis 인메모리 스토어",
]

# 태그 목록
AVAILABLE_TAGS = [
    "python", "javascript", "react", "nextjs", "fastapi", "django",
    "ml", "ai", "data-science", "web-dev", "frontend", "backend",
    "database", "postgresql", "redis", "docker", "kubernetes",
    "tutorial", "documentation", "guide", "tool", "framework"
]

# 추출 타입
EXTRACT_TYPES = ["content", "metadata", "summary", "keywords", "images"]

# 우선순위 레벨
PRIORITY_LEVELS = ["high", "medium", "low"]


def generate_random_user_id() -> int:
    """랜덤 사용자 ID 생성"""
    return random.randint(*USER_ID_RANGE)


def generate_session_id() -> str:
    """고유 세션 ID 생성"""
    return str(uuid.uuid4())


def generate_request_id() -> str:
    """고유 요청 ID 생성"""
    return str(uuid.uuid4())


def get_random_chat_message() -> str:
    """랜덤 채팅 메시지 반환"""
    return random.choice(CHAT_MESSAGES)


def get_random_url_and_title() -> tuple[str, str]:
    """랜덤 URL과 제목 쌍 반환"""
    index = random.randint(0, len(TEST_URLS) - 1)
    return TEST_URLS[index], TEST_TITLES[index]


def get_random_tags(min_count: int = 1, max_count: int = 3) -> List[str]:
    """랜덤 태그 목록 생성"""
    count = random.randint(min_count, max_count)
    return random.sample(AVAILABLE_TAGS, min(count, len(AVAILABLE_TAGS)))


def get_random_extract_type() -> str:
    """랜덤 추출 타입 반환"""
    return random.choice(EXTRACT_TYPES)


def get_random_priority() -> str:
    """랜덤 우선순위 반환"""
    return random.choice(PRIORITY_LEVELS)


def generate_chat_payload(user_id: int = None, session_id: str = None) -> Dict[str, Any]:
    """채팅 요청 페이로드 생성"""
    return {
        "user_id": user_id or generate_random_user_id(),
        "message": get_random_chat_message(),
        "session_id": session_id or generate_session_id(),
        "stream": True
    }


def generate_bookmark_payload(user_id: int = None) -> Dict[str, Any]:
    """북마크 생성 페이로드 생성"""
    url, title = get_random_url_and_title()
    return {
        "user_id": user_id or generate_random_user_id(),
        "url": url,
        "title": title,
        "bookmark_id": str(uuid.uuid4()),
        "created_at": None,  # 실제 전송 시 설정
        "tags": get_random_tags()
    }


def generate_extract_data_payload(user_id: int = None) -> Dict[str, Any]:
    """데이터 추출 페이로드 생성"""
    url, _ = get_random_url_and_title()
    return {
        "user_id": user_id or generate_random_user_id(),
        "url": url,
        "extract_type": get_random_extract_type(),
        "request_id": generate_request_id(),
        "priority": get_random_priority()
    } 