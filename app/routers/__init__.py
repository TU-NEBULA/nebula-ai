"""
라우터 패키지

이 패키지는 FastAPI 애플리케이션에 포함된 모든 라우터를 관리합니다.

주요 기능:
- 채팅 요청 라우터
- 채팅 스트리밍 라우터
"""
from fastapi import FastAPI
from app.routers.chat_request import router as chat_request_router
from app.routers.chat_stream import router as chat_stream_router

def init_routers(app: FastAPI) -> None:
    """라우터 초기화 함수"""
    app.include_router(chat_request_router)
    app.include_router(chat_stream_router)
