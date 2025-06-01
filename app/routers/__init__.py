from fastapi import FastAPI
from app.routers.chat_request import router as chat_request_router
from app.routers.chat_stream import router as chat_stream_router

def init_routers(app: FastAPI) -> None:
    app.include_router(chat_request_router)
    app.include_router(chat_stream_router)
