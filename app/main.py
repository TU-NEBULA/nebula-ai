import nltk

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import embedding
from app.routers import extract_data
from app.routers import embedding_status
from app.routers import embed_check

from app.middlewares.headers_middleware import HeadersMiddleware

async def lifespan(app: FastAPI):
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab")
    yield 

app = FastAPI(lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용 (개발 환경에서만 사용)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 커스텀 미들웨어 추가
app.add_middleware(HeadersMiddleware)

# 라우터 등록
app.include_router(embedding.router, prefix="/api", tags=["embedding"])
app.include_router(extract_data.router, prefix="/api", tags=["extract_data"])
app.include_router(embedding_status.router)
app.include_router(embed_check.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Hello World"}


# todo
# todo 1: 키워드 추출 다시 확인
# todo 2: 임베딩 시간 줄이기 -> 키워드, 사진 추출 이후 트리거, 임베딩 진행