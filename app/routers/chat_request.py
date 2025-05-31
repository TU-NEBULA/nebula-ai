from fastapi import APIRouter, Body, status, Response
from app.models.chat import ChatRequestModel
from app.services.chat_service import enqueue_prompt

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post(
    "/request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="채팅 프롬프트 접수",
)
async def chat_request(prompt: ChatRequestModel = Body(...), response: Response = None):
    """
    1) 프롬프트를 MQ 큐에 넣고
    2) jobId를 202 응답 + Location 헤더로 반환
    """
    job_id = await enqueue_prompt(prompt)

    response.headers["Location"] = f"/chat/stream/{job_id}"

    return {"detail": "accepted", "jobId": job_id}
