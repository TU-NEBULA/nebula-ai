"""
1) FastAPI 가 jobId 전용 임시 큐를 만들고
2) RabbitMQ 워커가 publish 하는 chunk/end 메시지를
3) SSE(text/event-stream) 형식으로 브라우저·Spring 에 전달
"""

import asyncio, json, logging, uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, Path, HTTPException
from fastapi.responses import StreamingResponse
from aio_pika import IncomingMessage, ExchangeType, Message

from app.core.rabbit import get_rabbit_connection

router = APIRouter(prefix="/chat", tags=["Chat"])
log = logging.getLogger(__name__)

@asynccontextmanager
async def _sse_from_rabbit(job_id: str):
    """
    RabbitMQ 의 routing-key == job_id 메시지를
    SSE 프레임으로 변환해 yield.
    """
    conn = await get_rabbit_connection()
    ch = await conn.channel()
    q = await ch.declare_queue(exclusive=True, auto_delete=True)
    await q.bind(exchange="amq.direct", routing_key=job_id)

    async def _generator():
        try:
            async with q.iterator() as q_iter:
                async for msg in q_iter:
                    async with msg.process():
                        try:
                            payload = json.loads(msg.body)
                        except json.JSONDecodeError:
                            log.warning("Malformed JSON chunk, skip")
                            continue

                        # CHUNK 또는 END
                        if payload.get("type") == "chunk":
                            yield f"data:{payload['data']}\n\n"
                        elif payload.get("type") == "end":
                            yield "event:end\ndata:{}\n\n"
                            break
                        await asyncio.sleep(0) # 루프 양보
        finally:
            await conn.close()

    try:
        yield _generator()
    except Exception:
        await conn.close()
        raise

@router.get(
    "/stream/{job_id}",
    response_class=StreamingResponse,
    summary="채팅 결과 SSE 스트림",
)
async def chat_stream(job_id: str = Path(...)):
    cm = _sse_from_rabbit(job_id)

    async def event_generator():
        async with cm as gen:
            async for chunk in gen:
                yield chunk

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)
