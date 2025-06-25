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
from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.chat import ChatRequestModel
from app.repositories.chat_repository import ChatRepository
# 같은 패키지 내 서비스들은 상대 import 사용하지 않고 직접 인스턴스 생성


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
        try:
            return await self.rag_search_service.retrieve_context(user_id, message)
        except Exception as e:
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
            for content, metadata in ctx_blocks:
                rag_references.append({
                    "snippet": content,
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
        
        return await self.profile_update_service.update_user_ai_profile_after_chat(
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
        graph_payload = self.visualization_service.create_bookmark_visualization(ctx_blocks, request.message)
        
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

    async def _get_conversation_history(
        self, 
        session_id: uuid.UUID, 
        user_id: int,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """현재 세션의 대화 히스토리를 가져옵니다."""
        try:
            # 현재 세션의 메시지들을 가져옴 (현재 사용자 메시지 제외)
            messages = await ChatRepository.get_session_messages(
                session=None,
                session_id=session_id,
                user_id=user_id,
                limit=limit
            )
            
            # ChatMessage 객체를 딕셔너리로 변환
            conversation_history = []
            for message in messages:
                conversation_history.append({
                    "role": message.role,
                    "content": message.content
                })
            
            logger.info(f"📜 대화 히스토리 조회 - session_id: {session_id}, 메시지 수: {len(conversation_history)}")
            return conversation_history
            
        except Exception as e:
            logger.error(f"❌ 대화 히스토리 조회 실패: {e}")
            return []

    async def generate_session_title(self, user_message: str) -> str:
        """
        사용자의 첫 번째 메시지를 기반으로 적절한 세션 제목을 생성합니다.
        
        Args:
            user_message: 사용자의 첫 번째 메시지
            
        Returns:
            생성된 세션 제목 (최대 50자)
        """
        try:
            # 제목 생성을 위한 프롬프트
            title_prompt = f"""다음 사용자 메시지를 바탕으로 대화 세션의 적절한 제목을 생성해주세요.

사용자 메시지: "{user_message}"

요구사항:
- 한국어로 작성
- 최대 50자 이내
- 메시지의 핵심 주제나 의도를 간결하게 표현
- 구체적이고 의미있는 제목
- 특수문자나 이모지 사용 금지

예시:
- "Python 리스트 정렬 방법" (정렬에 대한 질문인 경우)
- "React 컴포넌트 최적화" (React 성능에 대한 질문인 경우)
- "데이터베이스 설계 조언" (DB 설계에 대한 질문인 경우)

제목만 응답해주세요:"""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # 간단한 제목 생성이므로 가벼운 모델 사용
                messages=[
                    {"role": "system", "content": "당신은 대화 제목을 생성하는 전문가입니다. 간결하고 명확한 제목을 만들어주세요."},
                    {"role": "user", "content": title_prompt}
                ],
                max_tokens=100,
                temperature=0.7,
                timeout=10.0  # 10초 타임아웃
            )
            
            generated_title = response.choices[0].message.content.strip()
            
            # 제목 길이 제한 및 정리
            if len(generated_title) > 50:
                generated_title = generated_title[:47] + "..."
                
            # 따옴표 제거
            generated_title = generated_title.strip('"\'')
            
            logger.info(f"🏷️ 세션 제목 생성 완료: '{generated_title}'")
            return generated_title
            
        except asyncio.TimeoutError:
            logger.warning("⏰ 제목 생성 타임아웃 - 기본 제목 사용")
            return self._generate_fallback_title(user_message)
        except Exception as e:
            logger.error(f"❌ 제목 생성 실패: {e} - 기본 제목 사용")
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