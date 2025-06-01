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

import json
import asyncio
import traceback
import uuid

from typing import List, Tuple, Dict, Any

import aio_pika
from aio_pika import IncomingMessage, Message, DeliveryMode, ExchangeType
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.callbacks.streaming_aiter import AsyncIteratorCallbackHandler
from langchain.callbacks.tracers import ConsoleCallbackHandler
import chromadb
from loguru import logger

from app.core.config import settings
from app.core.rabbit import get_rabbit_connection
from app.schemas.chat import ChatRequestModel

# 벡터 DB 싱글턴
_embeddings: OpenAIEmbeddings | None = None
_vectordb: Chroma | None = None
TOP_K = 10  # 검색 문서 수


def _get_vectordb() -> Chroma:
    global _embeddings, _vectordb
    if _vectordb:
        logger.debug("🔄 기존 벡터DB 인스턴스 재사용")
        return _vectordb

    logger.info("🗄️ 벡터DB 초기화 중...")
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
    logger.info("✅ 벡터DB 초기화 완료")
    return _vectordb


async def _retrieve_context(user_id: int, query: str) -> List[Tuple[str, Dict[str, Any]]]:
    logger.info(f"🔍 컨텍스트 검색 시작 - user_id: {user_id}, query: {query[:50]}...")
    vectordb = _get_vectordb()
    docs_scores = vectordb.similarity_search_with_score(query, k=TOP_K)
    results = [
        (getattr(doc, "snippet", doc.page_content[:160]), doc.metadata)
        for doc, _ in docs_scores
        if doc.metadata.get("user_id") == user_id
    ]
    logger.info(f"📊 검색 결과: {len(results)}개 문서 발견")
    return results


def _build_messages(prompt: str, ctx_blocks: List[Tuple[str, Dict[str, Any]]]):
    if ctx_blocks:
        joined = "\n".join(
            f"{i+1}. {m.get('title','(제목없음)')} | {m.get('url','')}\n{snip}"
            for i, (snip, m) in enumerate(ctx_blocks[:5])
        )
        ctx = f"[CONTEXT]\n{joined}\n"
        logger.info(f"📝 컨텍스트 구성 완료: {len(ctx_blocks)}개 블록")
    else:
        ctx = "[CONTEXT]\n(관련 문서를 찾지 못했습니다)\n"
        logger.warning("⚠️ 관련 문서를 찾지 못했습니다")

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
    # amq.direct exchange 사용 (SSE 엔드포인트가 이걸 구독함)
    exchange = await ch.declare_exchange("amq.direct", ExchangeType.DIRECT)

    await exchange.publish(
        Message(
            body=json.dumps(payload).encode(),
            correlation_id=corr_id,
            delivery_mode=DeliveryMode.NOT_PERSISTENT,
        ),
        routing_key=routing_key,
    )
    logger.debug(f"📤 청크 발송: {routing_key} - {payload.get('type', 'unknown')}")


async def on_chat_message(message: IncomingMessage):
    async with message.process():  # ack / reject 자동
        ch = message.channel
        logger.info(f"📨 채팅 메시지 수신: correlation_id={message.correlation_id}")

        try:
            req = ChatRequestModel.model_validate_json(message.body)
            logger.info(f"✅ 메시지 파싱 성공: user_id={req.user_id}")
        except Exception as e:
            logger.error(f"❌ 메시지 파싱 실패: {e}")
            return

        logger.info(f"🚀 채팅 처리 시작 - uid={req.user_id}, prompt={req.message[:60]}...")

        # RAG 검색
        try:
            ctx_blocks = await _retrieve_context(req.user_id, req.message)
        except Exception as e:
            logger.error(f"❌ 컨텍스트 검색 실패: {e}")
            ctx_blocks = []

        # LLM 스트림 설정
        logger.info("🤖 OpenAI LLM 호출 준비 중...")

        # API 키 확인
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key":
            logger.error("❌ OpenAI API 키가 설정되지 않았습니다")
            await publish_chunk(ch, routing_key, job_id, {"type": "end", "error": "OpenAI API 키가 설정되지 않았습니다"})
            return

        logger.info(f"🔑 API 키 확인됨: {settings.OPENAI_API_KEY[:10]}...")
        logger.info(f"🤖 모델: {settings.OPENAI_MODEL}")

        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            streaming=True,
            temperature=0.7,
            timeout=30,  # 명시적 타임아웃 설정
            max_retries=1,  # 재시도 제한
        )
        job_id = message.correlation_id or str(uuid.uuid4())
        routing_key = job_id  # publish 대상

        try:
            logger.info(f"🔄 LLM 작업 시작 - job_id={job_id}")

            # 스트림 방식 변경 - agenerate 대신 stream 사용
            messages = _build_messages(req.message, ctx_blocks)
            logger.info("📨 메시지 구성 완료, OpenAI 스트림 호출...")

            token_count = 0
            full_response = ""

            # 직접 스트림 호출 방식
            for chunk in llm.stream(messages):
                if chunk.content:
                    token_count += 1
                    full_response += chunk.content
                    logger.debug(f"📝 토큰 {token_count}: {chunk.content[:20]}...")
                    await publish_chunk(ch, routing_key, job_id, {"type": "chunk", "data": chunk.content})

            logger.info(f"✅ LLM 작업 완료 - {token_count}개 토큰 생성")

        except asyncio.TimeoutError:
            logger.error("⏰ LLM 작업 타임아웃")
            await publish_chunk(ch, routing_key, job_id, {"type": "end", "error": "작업 시간 초과"})
            return
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"❌ LLM 작업 실패: {e}")
            logger.error(f"📋 상세 오류: {tb}")
            await publish_chunk(ch, routing_key, job_id, {"type": "end", "error": str(e)})
            return

        # 그래프(또는 기타) 페이로드
        graph_payload = {"nodes": [], "edges": [], "layout": "force-3d"}
        await publish_chunk(ch, routing_key, job_id, {"type": "end", "data": graph_payload})
        logger.info(f"🎯 채팅 처리 완료 - uid={req.user_id}, jobId={job_id}")


async def start_chat_consumer():
    logger.info("💬 Chat Consumer 시작 준비...")

    try:
        conn = await get_rabbit_connection()
        logger.info("✅ RabbitMQ 연결 성공")

        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1)
        logger.info("✅ 채널 설정 완료")

        # durable queue 선언
        q = await ch.declare_queue(settings.CHAT_REQ_QUEUE, durable=True)
        logger.info(f"✅ 큐 선언 완료: {settings.CHAT_REQ_QUEUE}")

        logger.info(f"🎯 Chat consumer 대기 중: {settings.CHAT_REQ_QUEUE}")
        await q.consume(on_chat_message)

    except Exception as e:
        logger.error(f"❌ Chat Consumer 시작 실패: {e}")
        raise
