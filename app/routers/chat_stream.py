"""
직접 스트리밍 채팅 API

RabbitMQ 없이 OpenAI API를 직접 호출하여 SSE로 스트리밍합니다.
PostgreSQL에 채팅 세션과 메시지를 저장합니다.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Tuple

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from sqlalchemy.ext.asyncio import AsyncSession
import chromadb
from loguru import logger

from app.core.config import settings
from app.core.database import get_async_session
from app.schemas.chat import ChatRequestModel, ChatStreamRequest
from app.repositories.chat_repository import ChatRepository

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
        for doc, score in docs_scores
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


async def _generate_chat_stream(
    request: ChatRequestModel, 
    db_session: AsyncSession,
    session_id: uuid.UUID,
    user_message_id: uuid.UUID
):
    """OpenAI 스트림을 SSE 형식으로 변환하면서 PostgreSQL에 저장"""
    try:
        logger.info(f"🚀 채팅 스트림 시작 - user_id: {request.user_id}, session_id: {session_id}")

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

        # AI 응답 수집 및 스트림
        ai_response = ""
        token_count = 0
        start_time = datetime.utcnow()

        for chunk in llm.stream(messages):
            if chunk.content:
                token_count += 1
                ai_response += chunk.content
                logger.debug(f"📝 토큰 {token_count}: {chunk.content[:20]}...")
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content})}\n\n"

        end_time = datetime.utcnow()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(f"✅ 스트림 완료 - {token_count}개 토큰 생성, 응답시간: {response_time_ms}ms")

        # AI 응답 메시지 저장
        ai_message = await ChatRepository.save_message(
            session=db_session,
            session_id=session_id,
            content=ai_response,
            role="assistant",
            user_id=request.user_id,
            metadata={
                "response_time_ms": response_time_ms,
                "token_count": token_count,
                "model": settings.OPENAI_MODEL
            }
        )

        # RAG 참조 저장
        if ctx_blocks:
            rag_references = []
            for snippet, metadata in ctx_blocks:
                rag_references.append({
                    "snippet": snippet,
                    "title": metadata.get("title", ""),
                    "url": metadata.get("url", ""),
                    "source_id": metadata.get("source_id", ""),
                    "score": 0.0  # similarity_search_with_score에서 점수 추출 필요
                })
            
            await ChatRepository.save_rag_references(
                session=db_session,
                message_id=ai_message.id,
                references=rag_references
            )

        # 완료 메시지 (그래프 데이터 포함)
        graph_payload = {"nodes": [], "edges": [], "layout": "force-3d"}
        completion_data = {
            "type": "end", 
            "data": graph_payload,
            "session_id": str(session_id),
            "message_id": str(ai_message.id)
        }
        yield f"data: {json.dumps(completion_data)}\n\n"

    except Exception as e:
        logger.error(f"❌ 스트림 생성 실패: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="채팅 스트림 (PostgreSQL 연동)",
)
async def chat_stream_direct(
    request: ChatRequestModel,
    db_session: AsyncSession = Depends(get_async_session)
):
    """
    직접 스트리밍 방식의 채팅 API with PostgreSQL 연동
    - 채팅 세션 관리
    - 메시지 저장
    - RAG 메타데이터 저장
    """
    logger.info(f"📨 채팅 스트림 요청 수신 - user_id: {request.user_id}")

    try:
        # 새로운 채팅 세션 생성 (매번 새로운 세션)
        # TODO: session_id가 제공되면 기존 세션 사용하도록 개선
        chat_session = await ChatRepository.create_session(
            session=db_session,
            user_id=request.user_id,
            title=f"대화 {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        
        # 사용자 메시지 저장
        user_message = await ChatRepository.save_message(
            session=db_session,
            session_id=chat_session.id,
            content=request.message,
            role="user",
            user_id=request.user_id
        )

        logger.info(f"💾 세션 및 사용자 메시지 저장 완료 - session_id: {chat_session.id}")

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }

        return StreamingResponse(
            _generate_chat_stream(request, db_session, chat_session.id, user_message.id),
            media_type="text/event-stream",
            headers=headers
        )

    except Exception as e:
        logger.error(f"❌ 채팅 스트림 초기화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"채팅 스트림 초기화 실패: {str(e)}")


# 채팅 세션 관리 API 추가
@router.get(
    "/sessions",
    summary="사용자 채팅 세션 목록 조회"
)
async def get_user_sessions(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    db_session: AsyncSession = Depends(get_async_session)
):
    """사용자의 채팅 세션 목록을 조회합니다."""
    try:
        sessions = await ChatRepository.get_user_sessions(
            session=db_session,
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        return {
            "sessions": [
                {
                    "id": str(session.id),
                    "title": session.title,
                    "session_type": session.session_type,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "is_active": session.is_active
                }
                for session in sessions
            ],
            "total": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"❌ 세션 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"세션 목록 조회 실패: {str(e)}")


@router.get(
    "/sessions/{session_id}/messages",
    summary="채팅 세션 메시지 조회"
)
async def get_session_messages(
    session_id: str,
    user_id: int,
    db_session: AsyncSession = Depends(get_async_session)
):
    """특정 채팅 세션의 메시지 목록을 조회합니다."""
    try:
        session_uuid = uuid.UUID(session_id)
        messages = await ChatRepository.get_session_messages(
            session=db_session,
            session_id=session_uuid,
            user_id=user_id
        )
        
        return {
            "session_id": session_id,
            "messages": [
                {
                    "id": str(message.id),
                    "content": message.content,
                    "role": message.role,
                    "created_at": message.created_at,
                    "metadata": message.metadata
                }
                for message in messages
            ]
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="올바르지 않은 세션 ID 형식입니다")
    except Exception as e:
        logger.error(f"❌ 세션 메시지 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"세션 메시지 조회 실패: {str(e)}")


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
