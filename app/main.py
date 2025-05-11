import os
import nltk
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.consumers.extract_data_rmq import start_extract_consumer
from app.consumers.chat_request_rmq import start_chat_consumer
from app.consumers.bookmark_save_rmq import start_bookmark_save_consumer

from app.core.config import settings

os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
os.environ.setdefault("LANGCHAIN_API_KEY", getattr(settings, "LANGSMITH_API_KEY", ""))
os.environ.setdefault("LANGCHAIN_PROJECT", getattr(settings, "LANGSMITH_PROJECT", "nebula-chatbot"))

async def lifespan(app: FastAPI):
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab")
    
    extract_task = asyncio.create_task(start_extract_consumer())
    chat_task = asyncio.create_task(start_chat_consumer())
    bookmark_save_task = asyncio.create_task(start_bookmark_save_consumer())
    print("모든 RabbitMQ consumer가 성공적으로 시작되었습니다")

    yield 

    extract_task.cancel()
    chat_task.cancel()
    bookmark_save_task.cancel()
    print("모든 RabbitMQ consumer가 종료되었습니다")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}
