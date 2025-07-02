"""
채팅 스트리밍 서비스

OpenAI API를 이용한 스트리밍 채팅과 관련 로직을 처리합니다.
"""

import json
import uuid
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, AsyncGenerator

from langchain_openai import ChatOpenAI
from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.monitoring import get_prometheus_metrics
from app.schemas.chat import ChatRequestModel
from app.repositories.chat_repository import ChatRepository
# 같은 패키지 내 서비스들은 상대 import 사용하지 않고 직접 인스턴스 생성

prometheus_metrics = get_prometheus_metrics()


class ChatStreamService:
    """채팅 스트리밍을 담당하는 서비스 클래스"""
    
    def __init__(self):
        self.buffer_size = 5  # 토큰 버퍼 크기
        self.progress_interval = 10  # 진행상황 알림 간격
        self.stream_delay = 0.01  # 스트리밍 지연 (10ms)
        
        # 다른 서비스들 인스턴스 생성
        from .rag_search_service import RAGSearchService
        from .message_builder_service import MessageBuilderService
        from .visualization_service import VisualizationService
        from .profile_update_service import ProfileUpdateService
        
        self.rag_search_service = RAGSearchService()
        self.message_builder_service = MessageBuilderService()
        self.visualization_service = VisualizationService()
        self.profile_update_service = ProfileUpdateService()
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
    async def generate_chat_stream(
        self,
        request: ChatRequestModel,
        session_id: uuid.UUID,
        user_message_id: uuid.UUID,
        messages: List[Dict[str, str]] = None
    ) -> AsyncGenerator[str, None]:
        """채팅 스트림 생성 (내부 메서드)"""
        start_time = datetime.now(timezone.utc)
        
        try:
            # 세션 시작 알림
            yield await self._create_session_start_message(session_id, user_message_id)

            # RAG 검색 수행
            ctx_blocks = await self._perform_rag_search(request.user_id, request.message)

            # 메시지 구성 (라우터에서 전달되지 않은 경우에만)
            if messages is None:
                # 대화 히스토리 가져오기
                conversation_history = await self._get_conversation_history(
                    session_id, request.user_id, limit=20
                )
                
                # 메시지 구성 (히스토리 포함)
                messages = self.message_builder_service.build_messages(
                    request.message, ctx_blocks, conversation_history
                )

            # 시각화 데이터 전송
            yield await self._create_visualization_message(ctx_blocks, request.message)

            # LLM 설정 및 스트리밍
            ai_response = ""
            async for chunk_data in self._stream_llm_response(messages, ctx_blocks):
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
        start_time = time.time()
        try:
            result = await self.rag_search_service.retrieve_context(user_id, message)
            
            # 벡터 검색 메트릭 기록
            duration = time.time() - start_time
            prometheus_metrics.increment_vector_operations("rag_search", "success")
            prometheus_metrics.record_external_api_call("vector_search", "rag_search", duration)
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            prometheus_metrics.increment_vector_operations("rag_search", "error")
            prometheus_metrics.record_external_api_call("vector_search", "rag_search_error", duration)
            logger.error(f"❌ 컨텍스트 검색 실패: {e}")
            return []

    async def _create_visualization_message(
        self, 
        ctx_blocks: List[Tuple[str, Dict[str, Any]]], 
        search_query: str
    ) -> str:
        """시각화 데이터 메시지 생성"""
        viz_message = self.visualization_service.create_visualization_message(ctx_blocks, search_query)
        
        if ctx_blocks:
            logger.info(f"📊 시각화 데이터 전송 완료 - 노드: {len(viz_message['data']['graph_payload']['nodes'])}개")
        
        return f"data: {json.dumps(viz_message, ensure_ascii=False)}\n\n"

    async def _stream_llm_response(
        self, 
        messages: List[Dict[str, str]],
        ctx_blocks: List[Tuple[str, Dict[str, Any]]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """LLM 응답 스트리밍"""
        start_time = time.time()
        logger.info("🤖 OpenAI LLM 호출 준비 중...")
        
        try:
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
            
            # OpenAI API 호출 메트릭 기록
            duration = time.time() - start_time
            prometheus_metrics.record_external_api_call("openai", "chat_completion", duration)
            logger.info(f"🤖 OpenAI LLM 응답 완료 - 토큰: {token_count}개 (소요시간: {duration:.2f}초)")
            
        except Exception as e:
            duration = time.time() - start_time
            prometheus_metrics.record_external_api_call("openai", "chat_completion_error", duration)
            logger.error(f"❌ LLM 응답 스트리밍 실패: {e}")
            raise

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
        """AI 응답을 데이터베이스에 저장"""
        save_start_time = time.time()
        try:
            chat_repo = ChatRepository()
            
            # AI 메시지 생성 및 저장
            ai_message = await chat_repo.save_ai_message(
                session_id=session_id,
                response=ai_response,
                user_id=user_id,
                duration=datetime.now(timezone.utc) - start_time
            )

            # RAG 참조 정보 저장
            if ctx_blocks:
                await self._save_rag_references(ai_message.id, ctx_blocks)

            # DB 저장 메트릭 기록
            duration = time.time() - save_start_time
            prometheus_metrics.record_database_query("insert", "chats", duration)
            
            logger.info(f"💾 AI 응답 저장 완료 - ID: {ai_message.id} (소요시간: {duration:.3f}초)")
            return ai_message

        except Exception as e:
            duration = time.time() - save_start_time
            prometheus_metrics.record_database_query("insert_error", "chats", duration)
            logger.error(f"❌ AI 응답 저장 실패: {e}")
            return None

    async def _save_rag_references(self, message_id: uuid.UUID, ctx_blocks: List[Tuple[str, Dict[str, Any]]]):
        """RAG 참조 정보 저장"""
        save_start_time = time.time()
        try:
            chat_repo = ChatRepository()
            
            for content_block, metadata in ctx_blocks:
                await chat_repo.save_rag_reference(
                    message_id=message_id,
                    source_type=metadata.get('source_type', 'unknown'),
                    source_id=metadata.get('source_id', ''),
                    relevance_score=float(metadata.get('score', 0.0)),
                    content_snippet=content_block[:500]  # 처음 500자만 저장
                )

            # RAG 참조 저장 메트릭 기록
            duration = time.time() - save_start_time
            prometheus_metrics.record_database_query("insert", "rag_references", duration)
            
            logger.debug(f"🔗 RAG 참조 {len(ctx_blocks)}개 저장 완료 (소요시간: {duration:.3f}초)")

        except Exception as e:
            duration = time.time() - save_start_time
            prometheus_metrics.record_database_query("insert_error", "rag_references", duration)
            logger.error(f"❌ RAG 참조 저장 실패: {e}")

    async def _update_user_profile(
        self,
        request: ChatRequestModel,
        ai_response: str,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        session_id: uuid.UUID,
        start_time: datetime
    ) -> Dict[str, Any]:
        """사용자 프로필 업데이트"""
        profile_start_time = time.time()
        try:
            # 프로필 업데이트 서비스 호출
            result = await self.profile_update_service.process_chat_interaction(
                user_id=request.user_id,
                user_message=request.message,
                ai_response=ai_response,
                context_blocks=ctx_blocks,
                session_id=str(session_id)
            )

            # 프로필 업데이트 메트릭 기록
            duration = time.time() - profile_start_time
            prometheus_metrics.record_database_query("update", "user_profiles", duration)
            
            logger.info(f"👤 사용자 프로필 업데이트 완료 - User ID: {request.user_id} (소요시간: {duration:.3f}초)")
            return result

        except Exception as e:
            duration = time.time() - profile_start_time
            prometheus_metrics.record_database_query("update_error", "user_profiles", duration)
            logger.error(f"❌ 사용자 프로필 업데이트 실패: {e}")
            return {"error": str(e)}

    async def _create_completion_message(
        self,
        ai_message,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        request: ChatRequestModel,
        start_time: datetime,
        profile_result: Dict[str, Any]
    ) -> str:
        """완료 메시지 생성"""
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        completion_data = {
            "type": "chat_complete",
            "data": {
                "message_id": str(ai_message.id) if ai_message else None,
                "session_id": str(request.session_id) if hasattr(request, 'session_id') else None,
                "user_id": request.user_id,
                "processing_time": round(processing_time, 2),
                "context_sources": len(ctx_blocks),
                "profile_updated": "error" not in profile_result,
                "profile_update_result": profile_result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        logger.info(f"✅ 채팅 완료 - 사용자: {request.user_id}, 처리시간: {processing_time:.2f}초, 컨텍스트: {len(ctx_blocks)}개")
        return f"data: {json.dumps(completion_data, ensure_ascii=False)}\n\n"

    async def _get_conversation_history(
        self, 
        session_id: uuid.UUID, 
        user_id: int,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """대화 히스토리 조회"""
        history_start_time = time.time()
        try:
            chat_repo = ChatRepository()
            messages = await chat_repo.get_session_messages(
                session_id=session_id, 
                user_id=user_id, 
                limit=limit
            )
            
            # 대화 히스토리를 langchain 형태로 변환
            conversation_history = []
            for msg in messages:
                if msg.message_type == "user":
                    conversation_history.append({
                        "role": "user",
                        "content": msg.content
                    })
                elif msg.message_type == "assistant":
                    conversation_history.append({
                        "role": "assistant", 
                        "content": msg.content
                    })

            # DB 조회 메트릭 기록
            duration = time.time() - history_start_time
            prometheus_metrics.record_database_query("select", "chats", duration)
            
            logger.debug(f"📚 대화 히스토리 조회 - 세션: {session_id}, 메시지: {len(conversation_history)}개 (소요시간: {duration:.3f}초)")
            return conversation_history

        except Exception as e:
            duration = time.time() - history_start_time
            prometheus_metrics.record_database_query("select_error", "chats", duration)
            logger.error(f"❌ 대화 히스토리 조회 실패: {e}")
            return []

    async def generate_session_title(self, user_message: str) -> str:
        """사용자 메시지를 기반으로 세션 제목 생성"""
        title_start_time = time.time()
        try:
            # 제목 생성을 위한 간단한 프롬프트
            title_prompt = [
                {
                    "role": "system",
                    "content": (
                        "사용자의 메시지를 바탕으로 간단하고 명확한 대화 제목을 한국어로 생성해주세요. "
                        "제목은 15자 이하로 작성하고, 대화의 핵심 주제를 담아주세요. "
                        "제목만 반환하고 다른 설명은 포함하지 마세요."
                    )
                },
                {
                    "role": "user", 
                    "content": f"다음 메시지의 제목을 생성해주세요: {user_message[:200]}"
                }
            ]

            # OpenAI API 호출
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=title_prompt,
                max_tokens=50,
                temperature=0.5,
                timeout=10
            )

            if response.choices and response.choices[0].message.content:
                title = response.choices[0].message.content.strip().replace('"', '')
                
                # 제목 생성 성공 메트릭
                duration = time.time() - title_start_time
                prometheus_metrics.record_external_api_call("openai", "title_generation", duration)
                
                logger.info(f"📝 세션 제목 생성 완료: '{title}' (소요시간: {duration:.2f}초)")
                return title
            else:
                # 응답이 없는 경우
                prometheus_metrics.record_external_api_call("openai", "title_generation_empty", time.time() - title_start_time)
                return self._generate_fallback_title(user_message)

        except Exception as e:
            duration = time.time() - title_start_time
            prometheus_metrics.record_external_api_call("openai", "title_generation_error", duration)
            logger.error(f"❌ 제목 생성 실패: {e}")
            return self._generate_fallback_title(user_message)
    
    def _generate_fallback_title(self, user_message: str) -> str:
        """
        AI 제목 생성 실패 시 사용할 폴백 제목 생성
        
        Args:
            user_message: 사용자 메시지
            
        Returns:
            폴백 제목
        """
        # 메시지의 첫 30자를 사용하여 간단한 제목 생성
        if len(user_message) <= 30:
            return user_message
        else:
            return user_message[:27] + "..."


# 싱글톤 인스턴스
chat_stream_service = ChatStreamService() 