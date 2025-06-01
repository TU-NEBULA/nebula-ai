"""
직접 스트리밍 채팅 API

RabbitMQ 없이 OpenAI API를 직접 호출하여 SSE로 스트리밍합니다.
"""

import json
from typing import Dict, Any, List, Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import chromadb
from loguru import logger

from app.core.config import settings
from app.schemas.chat import ChatRequestModel

router = APIRouter(prefix="/chat", tags=["Chat"])

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


async def _generate_chat_stream(request: ChatRequestModel):
    """OpenAI 스트림을 SSE 형식으로 변환"""
    try:
        logger.info(f"🚀 채팅 스트림 시작 - user_id: {request.user_id}")

        # API 키 확인
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key":
            logger.error("❌ OpenAI API 키가 설정되지 않았습니다")
            yield f"data: {json.dumps({'type': 'error', 'data': 'OpenAI API 키가 설정되지 않았습니다'})}\n\n"
            return

        # RAG 검색
        try:
            ctx_blocks = await _retrieve_context(request.user_id, request.message)
        except Exception as e:
            logger.error(f"❌ 컨텍스트 검색 실패: {e}")
            ctx_blocks = []

        # LLM 설정
        logger.info("🤖 OpenAI LLM 호출 준비 중...")
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            streaming=True,
            temperature=0.7,
            timeout=30,
            max_retries=1,
        )

        # 메시지 구성
        messages = _build_messages(request.message, ctx_blocks)
        logger.info("📨 OpenAI 스트림 호출 시작...")

        # 스트림 응답
        token_count = 0
        for chunk in llm.stream(messages):
            if chunk.content:
                token_count += 1
                logger.debug(f"📝 토큰 {token_count}: {chunk.content[:20]}...")
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content})}\n\n"

        logger.info(f"✅ 스트림 완료 - {token_count}개 토큰 생성")

        # 완료 메시지
        graph_payload = {"nodes": [], "edges": [], "layout": "force-3d"}
        yield f"data: {json.dumps({'type': 'end', 'data': graph_payload})}\n\n"

    except Exception as e:
        logger.error(f"❌ 스트림 생성 실패: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="채팅 스트림 (직접 방식)",
)
async def chat_stream_direct(request: ChatRequestModel):
    """
    직접 스트리밍 방식의 채팅 API
    RabbitMQ 없이 OpenAI를 직접 호출하여 SSE로 스트리밍
    """
    logger.info(f"📨 직접 스트림 요청 수신 - user_id: {request.user_id}")

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
    }

    return StreamingResponse(
        _generate_chat_stream(request),
        media_type="text/event-stream",
        headers=headers
    )


# 기존 RabbitMQ 기반 라우터도 유지 (호환성)
@router.get(
    "/stream/{job_id}",
    response_class=StreamingResponse,
    summary="채팅 결과 SSE 스트림 (레거시)",
)
async def chat_stream_legacy(job_id: str):
    """레거시 RabbitMQ 기반 스트림 (호환성 유지용)"""
    raise HTTPException(
        status_code=501,
        detail="RabbitMQ 기반 스트림은 더 이상 사용되지 않습니다. POST /chat/stream을 사용하세요."
    )
