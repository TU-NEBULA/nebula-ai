"""
Nebula AI 애플리케이션의 메인 진입점 모듈

이 모듈은 FastAPI 애플리케이션을 초기화하고 RabbitMQ 컨슈머를 시작하는 역할을 담당합니다.
애플리케이션 시작 시 NLTK 데이터를 확인하고, 필요한 경우 다운로드합니다.
또한 RabbitMQ 메시지를 비동기적으로 처리하기 위한 소비자 태스크를 생성하고 관리합니다.
"""

import asyncio

import nltk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.consumers.extract_data_rmq import start_extract_consumer
from app.consumers.chat_request_rmq import start_chat_consumer
from app.routers import init_routers

async def lifespan(_app: FastAPI):
    """
    FastAPI 애플리케이션의 수명 주기를 관리하는 함수

    애플리케이션이 시작될 때 필요한 리소스(NLTK 데이터, RabbitMQ 컨슈머)를 초기화하고,
    종료될 때 리소스를 정리합니다.

    Args:
        _app (FastAPI): FastAPI 애플리케이션 인스턴스

    Yields:
        None: FastAPI 애플리케이션이 실행되는 동안 yield를 통해 제어를 반환합니다.
    """
    # NLTK 데이터 확인 및 다운로드
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab")

    # 컨슈머 태스크 목록 초기화
    consumer_tasks = []

    try:
        # 추출 컨슈머 태스크 생성
        extract_task = asyncio.create_task(start_extract_consumer())
        consumer_tasks.append(extract_task)
        print("추출 컨슈머 태스크 생성됨")

        # 채팅 컨슈머 태스크 생성
        chat_task = asyncio.create_task(start_chat_consumer())
        consumer_tasks.append(chat_task)
        print("채팅 컨슈머 태스크 생성됨")

        print(f"총 {len(consumer_tasks)}개의 RabbitMQ 컨슈머 태스크가 생성됨")
    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"컨슈머 태스크 생성 실패: {e}")

    # FastAPI 애플리케이션 실행
    yield

    # 애플리케이션 종료 시 태스크 정리
    for task in consumer_tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

# FastAPI 애플리케이션 초기화
app = FastAPI(
    title="Nebula AI",
    description="NLP 기반 북마크 메모 서비스 인공지능 서버",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_routers(app)

@app.get("/", tags=["Health"])
async def root():
    """
    루트 엔드포인트 - 서버 상태 확인

    Returns:
        dict: 서버 상태 메시지
    """
    return {"message": "Hello World"}
