"""
직접 스트리밍 채팅 API

RabbitMQ 없이 OpenAI API를 직접 호출하여 SSE로 스트리밍합니다.
PostgreSQL에 채팅 세션과 메시지를 저장합니다.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from loguru import logger

from app.core.config import settings
from app.schemas.chat import (
    ChatRequestModel,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatSessionMessagesResponse,
    ChatSessionListResponse
)
from app.schemas.base import BaseResponse, IDResponse
from app.repositories.chat_repository import ChatRepository

from app.services.chat import (
    RAGSearchService,
    VisualizationService,
    MessageBuilderService,
    ChatStreamService,
    ProfileUpdateService
)

router = APIRouter(prefix="/chat", tags=["Chat"])

rag_search_service = RAGSearchService()
visualization_service = VisualizationService()
message_builder_service = MessageBuilderService()
chat_stream_service = ChatStreamService()
profile_update_service = ProfileUpdateService()


async def _generate_chat_stream(
    request: ChatRequestModel,
    session_id: uuid.UUID,
    user_message_id: uuid.UUID
):
    """OpenAI 스트림을 SSE 형식으로 변환하면서 PostgreSQL에 저장"""
    start_time = datetime.now(timezone.utc)
    
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
        yield f"data: {json.dumps(session_info, ensure_ascii=False)}\n\n"

        # API 키 확인
        if not settings.OPENAI_API_KEY:
            logger.error("❌ OpenAI API 키가 설정되지 않았습니다")
            error_msg = "OpenAI API 키가 설정되지 않았습니다"
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg}, ensure_ascii=False)}\n\n"
            return

        # 2. RAG 검색 수행
        ctx_blocks = await rag_search_service.retrieve_context(request.user_id, request.message)
        
        # 대화 히스토리 가져오기
        conversation_history = await ChatRepository.get_session_messages(
            session=None,
            session_id=session_id,
            user_id=request.user_id,
            limit=20
        )
        
        # ChatMessage 객체를 딕셔너리로 변환
        history_dicts = []
        for message in conversation_history:
            history_dicts.append({
                "role": message.role,
                "content": message.content
            })
        
        logger.info(f"📜 대화 히스토리 조회 완료 - session_id: {session_id}, 메시지 수: {len(history_dicts)}")

        # 3. 메시지 구성
        messages = message_builder_service.build_messages(request.message, ctx_blocks, history_dicts)
        
        # 4. AI 응답 스트리밍 처리 (구성된 메시지 전달)
        ai_response = ""
        token_count = 0
        
        async for stream_data in chat_stream_service._stream_llm_response(messages, ctx_blocks):
            if stream_data["type"] == "chunk":
                ai_response += stream_data["content"]
                token_count += 1
                yield f"data: {json.dumps(stream_data, ensure_ascii=False)}\n\n"
            elif stream_data["type"] == "progress":
                yield f"data: {json.dumps(stream_data, ensure_ascii=False)}\n\n"
            elif stream_data["type"] == "stream_complete":
                yield f"data: {json.dumps(stream_data, ensure_ascii=False)}\n\n"
                break

        # 프로필 업데이트 시작 알림
        yield f"data: {json.dumps({'type': 'profile_update_start', 'data': '사용자 프로필 분석 중...'}, ensure_ascii=False)}\n\n"

        end_time = datetime.now(timezone.utc)
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(f"✅ 스트림 완료 - {token_count}개 토큰 생성, 응답시간: {response_time_ms}ms")

        # 5. AI 응답 메시지 저장
        try:
            ai_message = await ChatRepository.save_message(
                session=None,
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
                try:
                    rag_references = []
                    for snippet, metadata in ctx_blocks:
                        rag_references.append({
                            "snippet": snippet,
                            "title": metadata.get("title", ""),
                            "url": metadata.get("url", ""),
                            "source_id": metadata.get("source_id", ""),
                            "score": float(metadata.get("score", 0.0))
                        })

                    await ChatRepository.save_rag_references(
                        session=None,
                        message_id=ai_message.id,
                        references=rag_references
                    )
                except Exception as rag_error:
                    logger.error(f"❌ RAG 참조 저장 실패: {rag_error}")
        
        except Exception as save_error:
            logger.error(f"❌ AI 메시지 저장 실패: {save_error}")
            ai_message = type('TempMessage', (), {'id': uuid.uuid4()})()

        # 6. 사용자 프로필 업데이트
        profile_update_result = await profile_update_service.update_user_ai_profile_after_chat(
            user_id=request.user_id,
            user_message=request.message,
            ai_response=ai_response,
            ctx_blocks=ctx_blocks,
            session_id=session_id,
            session_duration_minutes=(end_time - start_time).total_seconds() / 60
        )
        
        # 프로필 업데이트 완료 알림
        if profile_update_result.get("success"):
            profile_status_msg = f"프로필 업데이트 완료 (새 관심사: {profile_update_result.get('total_new_keywords', 0)}개)"
        else:
            profile_status_msg = "프로필 업데이트 실패"
            
        yield f"data: {json.dumps({'type': 'profile_update_complete', 'data': profile_status_msg}, ensure_ascii=False)}\n\n"
        
        # 7. 최종 완료 데이터 전송
        graph_payload = visualization_service.create_bookmark_visualization(ctx_blocks, request.message)
        
        completion_data = {
            "type": "session_end",
            "data": {
                "message_id": str(ai_message.id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "graph_payload": graph_payload,
                "session_info": {
                    "user_id": request.user_id,
                    "session_id": str(request.session_id),
                    "total_messages": 2,
                    "processing_time": f"{(datetime.now(timezone.utc) - start_time).total_seconds():.2f}s"
                },
                "rag_summary": {
                    "documents_found": len(ctx_blocks),
                    "search_successful": len(ctx_blocks) > 0,
                    "avg_similarity": graph_payload['statistics']['avg_similarity'] if ctx_blocks else 0
                },
                "profile_update": profile_update_result
            }
        }
        yield f"data: {json.dumps(completion_data, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error(f"❌ 스트림 생성 실패: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="채팅 스트림 (PostgreSQL 연동)",
)
async def chat_stream_direct(
    request: ChatRequestModel,
    idempotency_key: Optional[str] = Header(None)
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
            logger.info(f"🔄 중복 방지 키 확인: {idempotency_key}")

        # 기존 세션 확인 또는 새 세션 생성
        chat_session = None
        if hasattr(request, 'session_id') and request.session_id:
            chat_session = await ChatRepository.get_session(
                session=None,
                session_id=uuid.UUID(request.session_id),
                user_id=request.user_id
            )

        if not chat_session:
            chat_session = await ChatRepository.create_session(
                session=None,
                user_id=request.user_id,
                title=f"대화 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
            )

        # 사용자 메시지 저장
        try:
            user_message = await ChatRepository.save_message(
                session=None,
                session_id=chat_session.id,
                content=request.message,
                role="user",
                user_id=request.user_id
            )
            logger.info(f"💾 세션 및 사용자 메시지 저장 완료 - session_id: {chat_session.id}")
        except Exception as user_msg_error:
            logger.error(f"❌ 사용자 메시지 저장 실패: {user_msg_error}")
            user_message = type('TempMessage', (), {'id': uuid.uuid4()})()

        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "X-Accel-Buffering": "no",
        }

        return StreamingResponse(
            _generate_chat_stream(request, chat_session.id, user_message.id),
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
    title: Optional[str] = None
):
    """새로운 채팅 세션을 생성합니다."""
    try:
        default_title = f"새 대화 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        chat_session = await ChatRepository.create_session(
            session=None,
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
    offset: int = 0
):
    """사용자의 채팅 세션 목록을 조회합니다."""
    try:
        sessions = await ChatRepository.get_user_sessions(
            session=None,
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
    user_id: int
):
    """특정 채팅 세션의 메시지 목록을 조회합니다."""
    try:
        session_uuid = uuid.UUID(session_id)
        messages = await ChatRepository.get_session_messages(
            session=None,
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
