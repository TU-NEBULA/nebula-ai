"""
채팅 스트리밍 서비스

OpenAI API를 이용한 스트리밍 채팅과 관련 로직을 처리합니다.
"""

import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, AsyncGenerator

from langchain_openai import ChatOpenAI
from loguru import logger

from app.core.config import settings
from app.schemas.chat import ChatRequestModel
from app.repositories.chat_repository import ChatRepository
from app.services.rag_search_service import rag_search_service
from app.services.message_builder_service import message_builder_service
from app.services.visualization_service import visualization_service
from app.services.profile_update_service import profile_update_service


class ChatStreamService:
    """채팅 스트리밍을 담당하는 서비스 클래스"""
    
    def __init__(self):
        self.buffer_size = 5  # 토큰 버퍼 크기
        self.progress_interval = 10  # 진행상황 알림 간격
        self.stream_delay = 0.01  # 스트리밍 지연 (10ms)
        
    async def generate_chat_stream(
        self,
        request: ChatRequestModel,
        session_id: uuid.UUID,
        user_message_id: uuid.UUID
    ) -> AsyncGenerator[str, None]:
        """OpenAI 스트림을 SSE 형식으로 변환하면서 PostgreSQL에 저장"""
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(f"🚀 채팅 스트림 시작 - user_id: {request.user_id}, session_id: {session_id}")

            # 세션 시작 알림
            yield await self._create_session_start_message(session_id, user_message_id)

            # API 키 확인
            if not settings.OPENAI_API_KEY:
                yield await self._create_error_message("OpenAI API 키가 설정되지 않았습니다")
                return

            # RAG 검색 수행
            ctx_blocks = await self._perform_rag_search(request.user_id, request.message)

            # 시각화 데이터 전송
            yield await self._create_visualization_message(ctx_blocks, request.message)

            # LLM 설정 및 스트리밍
            ai_response = ""
            async for chunk_data in self._stream_llm_response(request, ctx_blocks):
                if chunk_data["type"] == "content":
                    ai_response += chunk_data["content"]
                yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"

            # 응답 저장 및 프로필 업데이트
            ai_message = await self._save_ai_response(
                session_id, ai_response, request.user_id, start_time, ctx_blocks
            )
            
            # 프로필 업데이트
            profile_result = await self._update_user_profile(
                request, ai_response, ctx_blocks, session_id, start_time
            )

            # 완료 메시지
            yield await self._create_completion_message(
                ai_message, ctx_blocks, request, start_time, profile_result
            )

        except Exception as e:
            logger.error(f"❌ 스트림 생성 실패: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"

    async def _create_session_start_message(
        self, 
        session_id: uuid.UUID, 
        user_message_id: uuid.UUID
    ) -> str:
        """세션 시작 메시지 생성"""
        session_info = {
            "type": "session_start",
            "data": {
                "session_id": str(session_id),
                "user_message_id": str(user_message_id)
            }
        }
        return f"data: {json.dumps(session_info, ensure_ascii=False)}\n\n"

    async def _create_error_message(self, error_msg: str) -> str:
        """에러 메시지 생성"""
        logger.error(f"❌ {error_msg}")
        return f"data: {json.dumps({'type': 'error', 'data': error_msg}, ensure_ascii=False)}\n\n"

    async def _perform_rag_search(self, user_id: int, message: str) -> List[Tuple[str, Dict[str, Any]]]:
        """RAG 검색 수행"""
        try:
            return await rag_search_service.retrieve_context(user_id, message)
        except Exception as e:
            logger.error(f"❌ 컨텍스트 검색 실패: {e}")
            return []

    async def _create_visualization_message(
        self, 
        ctx_blocks: List[Tuple[str, Dict[str, Any]]], 
        search_query: str
    ) -> str:
        """시각화 데이터 메시지 생성"""
        viz_message = visualization_service.create_visualization_message(ctx_blocks, search_query)
        
        if ctx_blocks:
            logger.info(f"📊 시각화 데이터 전송 완료 - 노드: {len(viz_message['data']['graph_payload']['nodes'])}개")
        
        return f"data: {json.dumps(viz_message, ensure_ascii=False)}\n\n"

    async def _stream_llm_response(
        self, 
        request: ChatRequestModel, 
        ctx_blocks: List[Tuple[str, Dict[str, Any]]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """LLM 응답 스트리밍"""
        logger.info("🤖 OpenAI LLM 호출 준비 중...")
        
        # LLM 설정
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            streaming=True,
            temperature=0.7,
            timeout=30,
            max_retries=1,
            model_kwargs={
                "stream_options": {"include_usage": False},
            }
        )

        # 메시지 구성
        messages = message_builder_service.build_messages(request.message, ctx_blocks)
        
        # 스트리밍 시작 알림
        yield {
            "type": "stream_start", 
            "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
        }

        # 응답 스트리밍
        token_count = 0
        chunk_buffer = ""

        for chunk in llm.stream(messages):
            if chunk.content:
                token_count += 1
                chunk_buffer += chunk.content
                
                should_send = self._should_send_chunk(chunk_buffer, chunk.content, token_count)
                
                if should_send:
                    logger.debug(f"📝 토큰 {token_count}: 청크 전송 - {chunk_buffer[:20]}...")
                    yield {"type": "chunk", "data": chunk_buffer, "content": chunk_buffer}
                    chunk_buffer = ""
                    
                    # 진행 상황 알림
                    if token_count % self.progress_interval == 0:
                        yield {
                            "type": "progress", 
                            "data": {"token_count": token_count, "status": "generating"}
                        }
                    
                    await asyncio.sleep(self.stream_delay)
        
        # 남은 버퍼 전송
        if chunk_buffer:
            logger.debug(f"📝 마지막 청크 전송: {chunk_buffer}")
            yield {"type": "chunk", "data": chunk_buffer, "content": chunk_buffer}
        
        # 스트리밍 완료
        yield {"type": "stream_complete", "data": "응답 생성 완료"}
        logger.info(f"✅ 스트림 완료 - {token_count}개 토큰 생성")

    def _should_send_chunk(self, chunk_buffer: str, current_content: str, token_count: int) -> bool:
        """청크 전송 여부 결정"""
        return (
            len(chunk_buffer) >= self.buffer_size or
            current_content in ['.', '!', '?', '\n', '。', '！', '？'] or
            token_count % 3 == 0
        )

    async def _save_ai_response(
        self,
        session_id: uuid.UUID,
        ai_response: str,
        user_id: int,
        start_time: datetime,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]]
    ):
        """AI 응답 저장"""
        try:
            end_time = datetime.now(timezone.utc)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # AI 메시지 저장
            ai_message = await ChatRepository.save_message(
                session=None,
                session_id=session_id,
                content=ai_response,
                role="assistant",
                user_id=user_id,
                metadata={
                    "response_time_ms": response_time_ms,
                    "token_count": len(ai_response.split()),  # 간단한 토큰 추정
                    "model": settings.OPENAI_MODEL
                }
            )

            # RAG 참조 저장
            if ctx_blocks:
                await self._save_rag_references(ai_message.id, ctx_blocks)

            return ai_message

        except Exception as save_error:
            logger.error(f"❌ AI 메시지 저장 실패: {save_error}")
            return type('TempMessage', (), {'id': uuid.uuid4()})()

    async def _save_rag_references(self, message_id: uuid.UUID, ctx_blocks: List[Tuple[str, Dict[str, Any]]]):
        """RAG 참조 정보 저장"""
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
                message_id=message_id,
                references=rag_references
            )
        except Exception as rag_error:
            logger.error(f"❌ RAG 참조 저장 실패: {rag_error}")

    async def _update_user_profile(
        self,
        request: ChatRequestModel,
        ai_response: str,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        session_id: uuid.UUID,
        start_time: datetime
    ) -> Dict[str, Any]:
        """사용자 프로필 업데이트"""
        end_time = datetime.now(timezone.utc)
        session_duration_minutes = (end_time - start_time).total_seconds() / 60
        
        return await profile_update_service.update_user_ai_profile_after_chat(
            user_id=request.user_id,
            user_message=request.message,
            ai_response=ai_response,
            ctx_blocks=ctx_blocks,
            session_id=session_id,
            session_duration_minutes=session_duration_minutes
        )

    async def _create_completion_message(
        self,
        ai_message,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        request: ChatRequestModel,
        start_time: datetime,
        profile_result: Dict[str, Any]
    ) -> str:
        """완료 메시지 생성"""
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
                "profile_update": profile_result
            }
        }
        return f"data: {json.dumps(completion_data, ensure_ascii=False)}\n\n"


# 싱글톤 인스턴스
chat_stream_service = ChatStreamService() 