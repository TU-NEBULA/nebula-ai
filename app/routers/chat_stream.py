"""
직접 스트리밍 채팅 API

RabbitMQ 없이 OpenAI API를 직접 호출하여 SSE로 스트리밍합니다.
PostgreSQL에 채팅 세션과 메시지를 저장합니다.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.config import settings
from app.core.database import get_async_session
from app.schemas.chat import (
    ChatRequestModel,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatSessionMessagesResponse,
    ChatSessionListResponse
)
from app.schemas.base import BaseResponse, IDResponse
from app.repositories.chat_repository import ChatRepository
from app.services.vector_service import vector_service

router = APIRouter(prefix="/chat", tags=["Chat"])

TOP_K = 10  # 검색 문서 수


async def _retrieve_context(
    user_id: int, query: str, session: AsyncSession = None
) -> List[Tuple[str, Dict[str, Any]]]:
    """PostgreSQL 벡터 데이터베이스에서 컨텍스트 검색"""
    logger.info(f"🔍 컨텍스트 검색 시작 - user_id: {user_id}, query: {query[:50]}...")

    if session is None:
        async for db_session in get_async_session():
            return await _retrieve_context(user_id, query, db_session)

    # PostgreSQL 벡터 검색 수행
    search_results = await vector_service.similarity_search(
        session=session,
        query=query,
        user_id=str(user_id),
        limit=TOP_K,
        similarity_threshold=0.7
    )

    # 검색 결과를 기존 포맷으로 변환
    results = []
    for document, score in search_results:
        snippet = document.content[:160].replace("\n", " ")
        metadata = {
            "title": document.title or "(제목없음)",
            "url": document.url or "",
            "source_id": document.source_id,
            "source_type": document.source_type,
            "keywords": document.keywords or [],
            "score": score
        }
        results.append((snippet, metadata))

    logger.info(f"📊 검색 결과: {len(results)}개 문서 발견")
    return results


def _build_messages(prompt: str, ctx_blocks: List[Tuple[str, Dict[str, Any]]]):
    # TODO: 세션 기반 대화 히스토리 추가 필요
    # - conversation_history 매개변수 추가
    # - 이전 대화 메시지들을 messages 배열에 포함
    # - 토큰 제한 고려하여 최근 N개 메시지만 포함

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
        # TODO: 여기에 conversation_history 메시지들 추가
        # for msg in conversation_history:
        #     messages.append({"role": msg["role"], "content": msg["content"]})
        {"role": "user", "content": prompt},
    ]


async def _generate_chat_stream(  # pylint: disable=too-many-locals
    request: ChatRequestModel,
    db_session: AsyncSession,
    session_id: uuid.UUID,
    user_message_id: uuid.UUID
):
    """OpenAI 스트림을 SSE 형식으로 변환하면서 PostgreSQL에 저장"""
    try:
        logger.info(f"🚀 채팅 스트림 시작 - user_id: {request.user_id}, session_id: {session_id}")

        # 스트림 시작: 세션 정보 먼저 전송
        session_info = {
            "type": "session_start",
            "data": {
                "session_id": str(session_id),
                "user_message_id": str(user_message_id)
            }
        }
        yield f"data: {json.dumps(session_info)}\n\n"

        # API 키 확인
        if not settings.OPENAI_API_KEY:
            logger.error("❌ OpenAI API 키가 설정되지 않았습니다")
            error_msg = "OpenAI API 키가 설정되지 않았습니다"
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"
            return

        # TODO: 대화 히스토리 조회 추가
        # conversation_history = await _get_conversation_history(
        #     session_id=session_id,
        #     user_id=request.user_id,
        #     db_session=db_session,
        #     max_messages=10  # 최근 10개 메시지
        # )

        # RAG 검색
        try:
            ctx_blocks = await _retrieve_context(request.user_id, request.message, db_session)
        except Exception as e:  # pylint: disable=broad-exception-caught
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

        # 메시지 구성 (TODO: 히스토리 포함)
        messages = _build_messages(request.message, ctx_blocks)
        # TODO: messages = _build_messages(request.message, ctx_blocks, conversation_history)
        logger.info("📨 OpenAI 스트림 호출 시작...")

        # AI 응답 수집 및 스트림
        ai_response = ""
        token_count = 0
        start_time = datetime.now(timezone.utc)

        for chunk in llm.stream(messages):
            if chunk.content:
                token_count += 1
                ai_response += chunk.content
                logger.debug(f"📝 토큰 {token_count}: {chunk.content[:20]}...")
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content})}\n\n"

        end_time = datetime.now(timezone.utc)
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

        # 완료 메시지 (그래프 데이터 + 메시지 ID 포함)
        graph_payload = {"nodes": [], "edges": [], "layout": "force-3d"}
        completion_data = {
            "type": "session_end",
            "data": graph_payload,
            "session_id": str(session_id),
            "ai_message_id": str(ai_message.id),
            "user_message_id": str(user_message_id)
        }
        yield f"data: {json.dumps(completion_data)}\n\n"

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"❌ 스트림 생성 실패: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"


# TODO: 대화 히스토리 조회 함수 추가 필요
# async def _get_conversation_history(
#     session_id: uuid.UUID,
#     user_id: int,
#     db_session: AsyncSession,
#     max_messages: int = 10
# ) -> List[Dict[str, str]]:
#     """
#     세션의 이전 대화 기록을 조회하여 LLM 컨텍스트에 포함할 형태로 반환
#
#     Args:
#         session_id: 채팅 세션 ID
#         user_id: 사용자 ID
#         db_session: DB 세션
#         max_messages: 최대 메시지 수 (토큰 제한 고려)
#
#     Returns:
#         [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
#
#     고려사항:
#     - 토큰 제한: GPT 모델별 최대 토큰 수 고려
#     - 성능: 자주 조회되는 히스토리는 캐싱 고려
#     - 우선순위: 최근 메시지 우선, 중요도에 따른 필터링
#     """
#     pass


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="채팅 스트림 (PostgreSQL 연동)",
)
async def chat_stream_direct(
    request: ChatRequestModel,
    idempotency_key: Optional[str] = Header(None),
    db_session: AsyncSession = Depends(get_async_session)
):
    """
    직접 스트리밍 방식의 채팅 API with PostgreSQL 연동
    - 채팅 세션 관리
    - 메시지 저장
    - RAG 메타데이터 저장
    - 중복 요청 방지
    """
    logger.info(f"📨 채팅 스트림 요청 수신 - user_id: {request.user_id}, idempotency_key: {idempotency_key}")

    try:
        # TODO: Idempotency key를 사용한 중복 요청 방지
        if idempotency_key:
            # Redis 또는 임시 저장소에서 중복 체크 (여기서는 간단히 로그만)
            logger.info(f"🔄 중복 방지 키 확인: {idempotency_key}")

        # 기존 세션 확인 또는 새 세션 생성
        chat_session = None
        if hasattr(request, 'session_id') and request.session_id:
            # 기존 세션 사용
            chat_session = await ChatRepository.get_session(
                session=db_session,
                session_id=uuid.UUID(request.session_id),
                user_id=request.user_id
            )

        if not chat_session:
            # 새로운 세션 생성
            chat_session = await ChatRepository.create_session(
                session=db_session,
                user_id=request.user_id,
                title=f"대화 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
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
        raise HTTPException(
            status_code=500,
            detail=f"채팅 스트림 초기화 실패: {str(e)}"
        ) from e


# 🆕 세션 생성 API 추가
@router.post(
    "/sessions",
    response_model=BaseResponse[IDResponse],
    summary="새 채팅 세션 생성"
)
async def create_chat_session(
    user_id: int,
    title: Optional[str] = None,
    db_session: AsyncSession = Depends(get_async_session)
):
    """새로운 채팅 세션을 생성합니다."""
    try:
        default_title = f"새 대화 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        chat_session = await ChatRepository.create_session(
            session=db_session,
            user_id=user_id,
            title=title or default_title
        )

        return BaseResponse[IDResponse](
            success=True,
            message="채팅 세션이 성공적으로 생성되었습니다",
            data=IDResponse(id=chat_session.id)
        )

    except Exception as e:
        logger.error(f"❌ 세션 생성 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 생성 실패: {str(e)}"
        ) from e


# 채팅 세션 관리 API 추가
@router.get(
    "/sessions",
    response_model=BaseResponse[ChatSessionListResponse],
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

        session_responses = [
            ChatSessionResponse(
                id=str(session.id),
                title=session.title,
                session_type=session.session_type,
                created_at=session.created_at,
                updated_at=session.updated_at,
                is_active=session.is_active
            )
            for session in sessions
        ]

        session_list_response = ChatSessionListResponse(
            sessions=session_responses,
            total=len(sessions)
        )

        return BaseResponse[ChatSessionListResponse](
            success=True,
            message="채팅 세션 목록을 성공적으로 조회했습니다",
            data=session_list_response
        )

    except Exception as e:
        logger.error(f"❌ 세션 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 목록 조회 실패: {str(e)}"
        ) from e


@router.get(
    "/sessions/{session_id}/messages",
    response_model=BaseResponse[ChatSessionMessagesResponse],
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

        message_responses = [
            ChatMessageResponse(
                id=str(message.id),
                content=message.content,
                role=message.role,
                created_at=message.created_at,
                metadata=message.rag_metadata or {}
            )
            for message in messages
        ]

        session_messages_response = ChatSessionMessagesResponse(
            session_id=session_id,
            messages=message_responses
        )

        return BaseResponse[ChatSessionMessagesResponse](
            success=True,
            message="채팅 메시지 목록을 성공적으로 조회했습니다",
            data=session_messages_response
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="올바르지 않은 세션 ID 형식입니다"
        ) from exc
    except Exception as e:
        logger.error(f"❌ 세션 메시지 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 메시지 조회 실패: {str(e)}"
        ) from e
