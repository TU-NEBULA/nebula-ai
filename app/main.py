import nltk
import asyncio

from fastapi import FastAPI

from app.consumers.extract_data_rmq import start_extract_consumer
from app.consumers.chat_request_rmq import start_chat_consumer  

async def lifespan(app: FastAPI):
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab")
    
    # 컨슈머 시작을 위한 태스크 생성
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
    except Exception as e:
        print(f"컨슈머 태스크 생성 실패: {e}")

    yield
    
    # 애플리케이션 종료 시 모든 태스크 정리
    for task in consumer_tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}