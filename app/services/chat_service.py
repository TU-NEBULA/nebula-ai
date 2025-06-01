"""
채팅 서비스 모듈
─────────────────────────────────────────────────────────────────────────────
1) enqueue_prompt : 프롬프트를 RabbitMQ(exchange=chat.req)로 퍼블리시
2) stream_tokens  : RAG 검색 결과를 포함해 OpenAI 스트리밍 토큰 생성
─────────────────────────────────────────────────────────────────────────────
필요 환경변수
- OPENAI_API_KEY
- OPENAI_MODEL                (ex. gpt-4o-mini)
- OPENAI_EMBED_MODEL          (ex. text-embedding-3-small)
- CHROMA_DB_URI               (벡터 DB 경로)
"""
from __future__ import annotations

import os, json, uuid, logging, asyncio
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator, Dict, Any, List, Tuple

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from openai import AsyncOpenAI

# LangChain – RAG
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma

from app.core.config import settings
from app.models.chat import ChatRequestModel

logger = logging.getLogger(__name__)

_rmq_connection: Optional[aio_pika.RobustConnection] = None
_rmq_channel: Optional[aio_pika.abc.AbstractChannel] = None


async def _get_rmq_channel() -> aio_pika.abc.AbstractChannel:
    global _rmq_connection, _rmq_channel
    if _rmq_connection and not _rmq_connection.is_closed:
        return _rmq_channel  # type: ignore

    _rmq_connection = await aio_pika.connect_robust(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        login=settings.RABBITMQ_USERNAME,
        password=settings.RABBITMQ_PASSWORD,
    )
    _rmq_channel = await _rmq_connection.channel(publisher_confirms=True)
    await _rmq_channel.set_qos(prefetch_count=10)
    return _rmq_channel


async def enqueue_prompt(prompt: ChatRequestModel) -> str:
    """
    프롬프트를 MQ에 넣고, correlation_id(job_id)를 돌려준다.
    """
    channel = await _get_rmq_channel()

    job_id = str(uuid.uuid4())
    body_bytes = prompt.model_dump_json().encode()

    message = Message(
        body=body_bytes,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        correlation_id=job_id,
        message_id=job_id,
        timestamp=datetime.now(timezone.utc),
    )

    # default exchange를 사용하여 직접 queue에 발행
    await channel.default_exchange.publish(
        message,
        routing_key=settings.CHAT_REQ_QUEUE  # queue 이름을 routing key로 사용
    )
    logger.info("Prompt published: uid=%s jobId=%s", prompt.user_id, job_id)

    return job_id


_client: AsyncOpenAI | None = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client:
        return _client

    _client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        timeout=settings.OPENAI_TIMEOUT or 30.0,
    )
    return _client

_embeddings: OpenAIEmbeddings | None = None
_vectordb: Chroma | None = None
TOP_K = 8  # 검색 최대 문서수


def _get_vectorstore() -> Chroma:
    global _embeddings, _vectordb
    if _vectordb:
        return _vectordb
    _embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBED_MODEL)
    _vectordb = Chroma(
        persist_directory=settings.CHROMA_DB_URI,
        embedding_function=_embeddings,
        collection_name="nebula_html",
    )
    return _vectordb


async def _openai_token_generator(
    messages: List[Dict[str, Any]],
    model: str = settings.OPENAI_MODEL,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True,
    )

    async for chunk in response:
        if (delta := chunk.choices[0].delta) and delta.content:
            yield delta.content
            await asyncio.sleep(0)


async def _retrieve_context(query: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    쿼리와 유사한 문서를 반환.
    Returns:
        List[ (snippet, metadata) ]
    """
    vectorstore = _get_vectorstore()
    docs_scores = vectorstore.similarity_search_with_score(query, k=TOP_K)
    results: List[Tuple[str, Dict[str, Any]]] = []
    for doc, score in docs_scores:
        snippet = getattr(doc, "snippet", doc.page_content[:160]).replace("\n", " ")
        results.append((snippet, doc.metadata))
    return results


def _build_messages(prompt: str, context_blocks: List[Tuple[str, Dict[str, Any]]]):
    """
    RAG 컨텍스트를 포함한 ChatCompletion messages 배열 생성
    """
    if context_blocks:
        joined = "\n".join(
            f"{idx+1}. {meta.get('title','(제목없음)')} | {meta.get('url','')}\n{snippet}"
            for idx, (snippet, meta) in enumerate(context_blocks[:5])
        )
        context_section = f"[CONTEXT]\n{joined}\n"
    else:
        context_section = "[CONTEXT]\n(관련 문서를 찾지 못했습니다)\n"

    system_prompt = (
        "너는 NEBULA AI 비서야. CONTEXT 안의 정보를 우선적으로 사용해 "
        "한국어로 간결하고 정확하게 답변해. 출처 문서의 번호를 괄호로 함께 표시해."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": context_section},
        {"role": "user", "content": prompt},
    ]


async def stream_tokens(prompt: str) -> AsyncGenerator[str, None]:
    """
    RAG 기반으로 OpenAI 토큰(str)을 비동기로 스트림.
    """
    try:
        context_blocks = await _retrieve_context(prompt)
        messages = _build_messages(prompt, context_blocks)

        async for token in _openai_token_generator(messages):
            yield token

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("RAG/OpenAI streaming failed: %s", exc)
        raise
