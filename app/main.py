from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 라우터 추가
from app.routers import embedding
from app.middlewares.headers_middleware import HeadersMiddleware

app = FastAPI()

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

@app.get("/")
async def root():
    return {"message": "Hello World"}
