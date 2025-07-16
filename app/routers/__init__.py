"""
라우터 패키지

이 패키지는 FastAPI 애플리케이션에 포함된 모든 라우터를 관리합니다.

주요 기능:
- 채팅 스트리밍 라우터 (PostgreSQL 연동)
- 사용자 프로필 라우터 (프로필 조회, 추천, 유사 사용자 검색)
- 추천 시스템 라우터 (개인화 추천, 피드백 수집)
- 북마크 요약 라우터 (북마크 내용 AI 요약, SSE 스트리밍)
"""
from fastapi import FastAPI
from app.routers.chat_stream import router as chat_stream_router
from app.routers.profile import router as profile_router
from app.routers.recommendations import router as recommendations_router
from app.routers.analytics import router as analytics_router
from app.routers.bookmark_summary import router as bookmark_summary_router

def init_routers(app: FastAPI) -> None:
    """라우터 초기화 함수"""
    app.include_router(chat_stream_router)
    app.include_router(profile_router)
    app.include_router(recommendations_router)
    app.include_router(analytics_router)
    app.include_router(bookmark_summary_router)
