"""
채팅 요청 라우터 (레거시)

더 이상 사용되지 않습니다. POST /chat/stream을 사용하세요.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post(
    "/request",
    summary="채팅 프롬프트 접수 (레거시)",
)
async def chat_request_legacy():
    """
    레거시 RabbitMQ 기반 채팅 요청
    더 이상 사용되지 않습니다.
    """
    raise HTTPException(
        status_code=501,
        detail="RabbitMQ 기반 요청은 더 이상 사용되지 않습니다. POST /chat/stream을 사용하세요."
    )
