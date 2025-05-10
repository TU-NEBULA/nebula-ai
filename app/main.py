import nltk
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import embedding
from app.routers import extract_data
from app.routers import embed_check
from app.routers import keyword_sync
from app.routers import task_status

from app.middlewares.headers_middleware import HeadersMiddleware

from app.consumers.extract_data_rmq import start_extract_consumer

async def lifespan(app: FastAPI):
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab")
    
    try:
        await start_extract_consumer()
        print("RabbitMQ consumer started successfully")
    except Exception as e:
        print(f"Failed to start RabbitMQ consumer: {e}")

    # await asyncio.gather(
    #     start_extract_consumer(),
    #     start_bookmark_consumer(),
    #     start_summarize_consumer(),
    # )

    yield 

app = FastAPI(lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 커스텀 미들웨어
app.add_middleware(HeadersMiddleware)

# 라우터 등록
app.include_router(extract_data.router, prefix="/api", tags=["extract_data"])

app.include_router(embedding.router, prefix="/api", tags=["embedding"])
app.include_router(embed_check.router, prefix="/api", tags=["embedding"])

app.include_router(keyword_sync.router, prefix="/api", tags=["keyword"])

app.include_router(task_status.router, prefix="/api", tags=["task"])


@app.get("/")
async def root():
    return {"message": "Hello World"}
