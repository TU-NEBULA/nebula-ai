"""
chat_request_rmq.py
────────────────────────────────────────────────────────────────────────────
1. chat.req(exchange) ⇒ userId(routing_key) 로 들어온 프롬프트 메시지를 소비
2. Chroma 벡터DB에서 Top-K 문서를 검색해 RAG 컨텍스트 구성
3. LangChain ChatOpenAI(streaming) 으로 토큰 생성
4. 각 토큰·완료 이벤트를 amq.direct(exchange) ⇒ jobId(routing_key) 로 퍼블리시
   (FastAPI /chat/stream/{jobId} 엔드포인트가 이걸 구독해 SSE로 내보냄)
"""

from __future__ import annotations

import os, json, logging, asyncio, traceback, uuid
from typing import List, Tuple, Dict, Any

import aio_pika
from aio_pika import IncomingMessage, Message, DeliveryMode, ExchangeType
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.callbacks.streaming_aiter import AsyncIteratorCallbackHandler
from langchain.callbacks.tracers import ConsoleCallbackHandler
import chromadb

from app.core.config import settings
from app.core.rabbit import get_rabbit_connection
from app.models.chat import ChatRequestModel

log = logging.getLogger(__name__)

# 벡터 DB 싱글턴
_embeddings: OpenAIEmbeddings | None = None
_vectordb: Chroma | None = None
TOP_K = 10  # 검색 문서 수


def _get_vectordb() -> Chroma:
    global _embeddings, _vectordb
    if _vectordb:
        return _vectordb
    _embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBED_MODEL)
    _vectordb = Chroma(
        persist_directory=settings.CHROMA_DB_URI,
        embedding_function=_embeddings,
        collection_name="nebula_html",
        client_settings=chromadb.config.Settings(
            is_persistent=True,
            persist_directory=settings.CHROMA_DB_URI,
            anonymized_telemetry=False
        )
    )
    return _vectordb


async def _retrieve_context(user_id: int, query: str) -> List[Tuple[str, Dict[str, Any]]]:
    vectordb = _get_vectordb()
    docs_scores = vectordb.similarity_search_with_score(query, k=TOP_K)
    return [
        (getattr(doc, "snippet", doc.page_content[:160]), doc.metadata)
        for doc, _ in docs_scores
        if doc.metadata.get("user_id") == user_id
    ]


def _build_messages(prompt: str, ctx_blocks: List[Tuple[str, Dict[str, Any]]]):
    if ctx_blocks:
        joined = "\n".join(
            f"{i+1}. {m.get('title','(제목없음)')} | {m.get('url','')}\n{snip}"
            for i, (snip, m) in enumerate(ctx_blocks[:5])
        )
        ctx = f"[CONTEXT]\n{joined}\n"
    else:
        ctx = "[CONTEXT]\n(관련 문서를 찾지 못했습니다)\n"

    system_prompt = (
        "너는 NEBULA AI 비서야. CONTEXT 정보를 활용해 한국어로 간결하고 정확하게 답변해. "
        "출처 문서는 괄호로 번호를 표시해."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": ctx},
        {"role": "user", "content": prompt},
    ]


async def publish_chunk(
    ch: aio_pika.abc.AbstractChannel,
    routing_key: str,
    corr_id: str,
    payload: Dict[str, Any],
):
    await ch.default_exchange.publish(
        Message(
            body=json.dumps(payload).encode(),
            correlation_id=corr_id,
            delivery_mode=DeliveryMode.NOT_PERSISTENT,
        ),
        routing_key=routing_key,
    )


async def on_chat_message(message: IncomingMessage):
    async with message.process():  # ack / reject 자동
        ch = message.channel
        try:
            req = ChatRequestModel.model_validate_json(message.body)
        except Exception as e:
            log.error("Invalid message JSON: %s", e)
            return

        log.info("[ChatReq] uid=%s prompt=%.60s…", req.user_id, req.message)

        # RAG 검색
        ctx_blocks = await _retrieve_context(req.user_id, req.message)

        # LLM 스트림 설정
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            streaming=True,
            temperature=0.7,
            timeout=60,
        )
        stream_cb = AsyncIteratorCallbackHandler()
        job_id = message.correlation_id or str(uuid.uuid4())
        routing_key = job_id  # publish 대상

        try:
            # LLM 호출 태스크 실행
            llm_task = asyncio.create_task(
                llm.agenerate([_build_messages(req.message, ctx_blocks)], callbacks=[stream_cb, ConsoleCallbackHandler()])
            )

            # 토큰 소비 → publish_chunk
            async for chunk in stream_cb.aiter():
                if chunk.content:
                    await publish_chunk(ch, routing_key, job_id, {"type": "chunk", "data": chunk.content})

            await llm_task  # 실패 시 예외 전파
        except Exception:
            tb = traceback.format_exc()
            log.error("Worker error: %s", tb)
            await publish_chunk(ch, routing_key, job_id, {"type": "end", "error": tb})
            return

        # 그래프(또는 기타) 페이로드
        graph_payload = {"nodes": [], "edges": [], "layout": "force-3d"}
        await publish_chunk(ch, routing_key, job_id, {"type": "end", "data": graph_payload})
        log.info("[ChatDone] uid=%s jobId=%s", req.user_id, job_id)


async def start_chat_consumer():
    conn = await get_rabbit_connection()
    ch = await conn.channel()
    await ch.set_qos(prefetch_count=1)

    # 모든 사용자 요청을 하나의 durable 큐에서 소비
    q = await ch.declare_queue(settings.CHAT_REQ_QUEUE, durable=True)
    await q.bind("chat.req", routing_key="#")  # wildcard → 모든 userId

    log.info("Chat consumer listening on %s", settings.CHAT_REQ_QUEUE)
    await q.consume(on_chat_message)
