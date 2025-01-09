from fastapi import FastAPI, File, UploadFile
from app.routers import extract_data
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(HeadersMiddleware)

app.include_router(extract_data.router, prefix="/api", tags=["extract data"])

@app.get("/")
async def root():
    return {"message": "Hello World"}