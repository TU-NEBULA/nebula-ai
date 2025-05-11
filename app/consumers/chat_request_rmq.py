import json
import uuid
import logging
from aio_pika import IncomingMessage, Message
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from app.core.rabbit import get_rabbit_connection
from app.services.chat import process_chat_request
from app.core.config import settings

log = logging.getLogger(__name__)


class ChatRequestModel(BaseModel):
    user_id: int = Field(..., alias="userId")
    message: str

    class Config:
        allow_population_by_field_name = True


class BookmarkItemModel(BaseModel):
    id: str
    title: str
    url: str
    snippet: str


class GraphPayload(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    layout: str


class ChatResponseModel(BaseModel):
    answer: str
    graphPayload: GraphPayload = Field(..., alias="graphPayload")

    class Config:
        validate_by_name = True
        allow_population_by_field_name = True



async def on_chat_message(ch, message: IncomingMessage):
    async with message.process():
        try:
            # 요청 로그 추가
            print("Chat 요청 처리 시작 body=%s", message.body)

            req = ChatRequestModel.model_validate_json(message.body)
            print("Chat 요청 처리 중 userId=%s, message=%s", req.user_id, req.message)

            resp_data = await process_chat_request(
                user_id = req.user_id,
                message = req.message
            )

            # 레이아웃 값 검증 및 수정
            if resp_data.get("graphPayload", {}).get("layout", "") != "force-3d":
                log.warning("레이아웃 값이 예상과 다릅니다: %s", resp_data.get("graphPayload", {}).get("layout"))
                if "graphPayload" in resp_data and "layout" in resp_data["graphPayload"]:
                    resp_data["graphPayload"]["layout"] = "force-3d"

            try:
                chat_resp = ChatResponseModel.model_validate(resp_data)

                # reply_to가 있는지 확인
                if not message.reply_to:
                    log.error("reply_to가 없어 응답을 보낼 수 없습니다.")
                    return

                await ch.default_exchange.publish(
                    Message(
                        body = chat_resp.model_dump_json().encode(),
                        correlation_id = message.correlation_id or str(uuid.uuid4())
                    ),
                    routing_key=message.reply_to
                )

                print("Chat 처리 완료 userId=%s", req.user_id)

            except Exception as validation_error:
                log.error("응답 모델 검증 실패: %s, data=%s", str(validation_error), resp_data)
                # 오류 응답 전송
                error_resp = {
                    "error": f"응답 모델 검증 실패: {str(validation_error)}",
                    "graphPayload": {"nodes": [], "edges": [], "layout": "force-3d"}
                }

                if message.reply_to:
                    await ch.default_exchange.publish(
                        Message(
                            body = json.dumps(error_resp).encode(),
                            correlation_id = message.correlation_id or str(uuid.uuid4())
                        ),
                        routing_key=message.reply_to
                    )

        except Exception as e:
            log.error("Chat 처리 실패 error=%s body=%s", str(e), message.body)
            # 오류가 있어도 consumer는 계속 실행되어야 함
            # 클라이언트에게 오류 응답 전송
            try:
                if message.reply_to:
                    error_resp = {
                        "error": f"서버 오류: {str(e)}",
                        "graphPayload": {"nodes": [], "edges": [], "layout": "force-3d"}
                    }
                    await ch.default_exchange.publish(
                        Message(
                            body = json.dumps(error_resp).encode(),
                            correlation_id = message.correlation_id or str(uuid.uuid4())
                        ),
                        routing_key=message.reply_to
                    )
            except Exception as publish_error:
                log.error("오류 응답 전송 실패: %s", str(publish_error))


async def start_chat_consumer():
    conn = await get_rabbit_connection()
    ch   = await conn.channel()

    await ch.set_qos(prefetch_count=1)

    q = await ch.declare_queue(settings.CHAT_REQ_QUEUE, durable=True)
    async def handler(message: IncomingMessage):
        await on_chat_message(ch, message)
    await q.consume(handler)

    print(" [*] chat_request_rmq 리스너 시작, queue=%s", q.name)
