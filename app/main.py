from fastapi import FastAPI
from app.routers import keyword_extractor

app = FastAPI()

app.include_router(keyword_extractor.router, prefix="/api", tags=["keyword extractor"])

@app.get("/")
async def root():
    return {"message": "Hello World"}