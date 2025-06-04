"""
태스크 패키지 초기화

이 모듈은 모든 백그라운드 태스크들을 중앙에서 관리합니다.
Celery 워커가 자동으로 태스크들을 발견할 수 있도록 모든 태스크 모듈을 import합니다.
"""

# 북마크 관련 태스크
from .bookmark_save_task import save_bookmark_task

# 사용자 프로필 관련 태스크
from .user_profile_tasks import (
    update_user_profile_task,
    calculate_user_similarities_task,
    generate_recommendations_task,
    analyze_trends_task
)

# 내보낼 태스크들
__all__ = [
    # 북마크 태스크
    'save_bookmark_task',

    # 사용자 프로필 태스크
    'update_user_profile_task',
    'calculate_user_similarities_task',
    'generate_recommendations_task',
    'analyze_trends_task',
]
