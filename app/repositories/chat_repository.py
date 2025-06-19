"""
채팅 Repository

채팅 세션, 메시지, RAG 메타데이터에 대한 데이터 접근을 담당합니다.
Repository 패턴을 통해 데이터베이스 로직을 캡슐화합니다.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from loguru import logger
from sqlmodel import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import (
    ChatSession, ChatMessage, RAGReference, UserFeedback
)


class ChatRepository:
    """채팅 관련 데이터 접근을 처리하는 Repository"""

    @staticmethod
    async def create_session(
        session: AsyncSession,
        user_id: int,
        title: Optional[str] = None,
        session_type: str = "general"
    ) -> ChatSession:
        """새로운 채팅 세션을 생성합니다."""
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                chat_session = ChatSession(
                    user_id=user_id,
                    title=title or "새로운 대화",
                    session_type=session_type,
                    is_active=True
                )
                new_session.add(chat_session)
                await new_session.commit()
                await new_session.refresh(chat_session)

                logger.info(f"📝 새 채팅 세션 생성 - session_id: {chat_session.id}, user_id: {user_id}")
                return chat_session
                
            except Exception as e:
                logger.error(f"❌ 세션 생성 실패: {e}")
                try:
                    await new_session.rollback()
                except Exception as rollback_error:
                    logger.error(f"❌ 세션 생성 롤백 실패: {rollback_error}")
                raise

    @staticmethod
    async def get_session(
        session: AsyncSession,
        session_id: uuid.UUID,
        user_id: int
    ) -> Optional[ChatSession]:
        """특정 채팅 세션을 조회합니다."""
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                stmt = select(ChatSession).where(
                    and_(
                        ChatSession.id == session_id,
                        ChatSession.user_id == user_id  # int 형태로 비교
                    )
                )
                result = await new_session.execute(stmt)
                return result.scalar_one_or_none()
                
            except Exception as e:
                logger.error(f"❌ 세션 조회 실패: {e}")
                return None

    @staticmethod
    async def get_user_sessions(
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatSession]:
        """사용자의 채팅 세션 목록을 조회합니다."""
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                stmt = (
                    select(ChatSession)
                    .where(ChatSession.user_id == user_id)  # int 형태로 비교
                    .order_by(ChatSession.updated_at.desc())  # pylint: disable=no-member
                    .offset(offset)
                    .limit(limit)
                )
                result = await new_session.execute(stmt)
                return list(result.scalars().all())
                
            except Exception as e:
                logger.error(f"❌ 사용자 세션 목록 조회 실패: {e}")
                return []

    @staticmethod
    async def get_user_sessions_with_messages(
        session: AsyncSession,
        user_id: int,
        days: int = 30
    ) -> List[ChatSession]:
        """메시지가 포함된 사용자의 최근 채팅 세션을 조회합니다."""
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                recent_date = datetime.now(timezone.utc) - timedelta(days=days)

                stmt = (
                    select(ChatSession)
                    .where(
                        and_(
                            ChatSession.user_id == user_id,
                            ChatSession.updated_at >= recent_date
                        )
                    )
                    .options(selectinload(ChatSession.messages))
                    .order_by(ChatSession.updated_at.desc())  # pylint: disable=no-member
                )

                result = await new_session.execute(stmt)
                sessions = list(result.scalars().all())

                logger.debug(f"💬 사용자 {user_id} 최근 {days}일 세션 조회 - 총 {len(sessions)}개")
                return sessions
                
            except Exception as e:
                logger.error(f"❌ 메시지 포함 세션 조회 실패: {e}")
                return []

    @staticmethod
    async def get_user_recent_messages(
        session: AsyncSession,
        user_id: int,
        days: int = 30,
        role: str = "user",
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """사용자의 최근 메시지를 조회합니다."""
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                recent_date = datetime.now(timezone.utc) - timedelta(days=days)

                stmt = (
                    select(ChatMessage)
                    .where(
                        and_(
                            ChatMessage.user_id == user_id,
                            ChatMessage.role == role,
                            ChatMessage.created_at >= recent_date
                        )
                    )
                    .order_by(ChatMessage.created_at.desc())  # pylint: disable=no-member
                )

                if limit:
                    stmt = stmt.limit(limit)

                result = await new_session.execute(stmt)
                messages = list(result.scalars().all())

                logger.debug(f"📝 사용자 {user_id} 최근 {days}일 {role} 메시지 조회 - 총 {len(messages)}개")
                return messages
                
            except Exception as e:
                logger.error(f"❌ 최근 메시지 조회 실패: {e}")
                return []

    @staticmethod
    async def save_message(
        session: AsyncSession,
        session_id: uuid.UUID,
        content: str,
        role: str,
        user_id: int,
        **kwargs
    ) -> ChatMessage:
        """채팅 메시지를 저장합니다."""
        metadata = kwargs.get('metadata')
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                # 중복 메시지 방지를 위한 검증 (같은 세션, 같은 사용자, 같은 내용의 메시지가 최근 1분 내에 있는지 확인)
                recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)

                existing_message_stmt = select(ChatMessage).where(
                    and_(
                        ChatMessage.session_id == session_id,
                        ChatMessage.user_id == user_id,  # int 형태로 비교
                        ChatMessage.content == content,
                        ChatMessage.role == role,
                        ChatMessage.created_at >= recent_time
                    )
                )
                
                try:
                    existing_result = await new_session.execute(existing_message_stmt)
                    existing_message = existing_result.scalar_one_or_none()

                    if existing_message:
                        logger.warning(f"⚠️ 중복 메시지 감지 - 기존 메시지 반환: {existing_message.id}")
                        return existing_message
                except Exception as e:
                    logger.warning(f"⚠️ 중복 메시지 확인 중 오류 (무시하고 계속): {e}")
                    # 중복 확인 실패시에도 메시지 저장을 계속 진행

                message = ChatMessage(
                    session_id=session_id,
                    content=content,
                    role=role,
                    user_id=user_id,  # int 형태 그대로 사용
                    rag_metadata=metadata or {}
                )
                new_session.add(message)
                await new_session.commit()
                await new_session.refresh(message)

                logger.debug(f"💾 메시지 저장 - session_id: {session_id}, role: {role}")
                return message

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(f"❌메시지 저장 실패: {e}")
                try:
                    await new_session.rollback()
                except Exception as rollback_error:
                    logger.error(f"❌ 롤백 실패: {rollback_error}")
                raise

    @staticmethod
    async def get_session_messages(
        session: AsyncSession,
        session_id: uuid.UUID,
        user_id: int,
        limit: int = 100
    ) -> List[ChatMessage]:
        """채팅 세션의 메시지 목록을 조회합니다."""
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                stmt = (
                    select(ChatMessage)
                    .where(
                        and_(
                            ChatMessage.session_id == session_id,
                            ChatMessage.user_id == user_id  # int 형태로 비교
                        )
                    )
                    .order_by(ChatMessage.created_at.asc())  # pylint: disable=no-member
                    .limit(limit)
                )
                result = await new_session.execute(stmt)
                return list(result.scalars().all())
                
            except Exception as e:
                logger.error(f"❌ 세션 메시지 조회 실패: {e}")
                return []

    @staticmethod
    async def save_rag_references(
        session: AsyncSession,
        message_id: uuid.UUID,
        references: List[Dict[str, Any]]
    ) -> List[RAGReference]:
        """RAG 참조 문서들을 저장합니다."""
        
        # 새로운 독립적인 트랜잭션으로 처리
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as new_session:
            try:
                rag_refs = []
                for idx, ref in enumerate(references):
                    rag_ref = RAGReference(
                        message_id=message_id,
                        source_type="vector",  # PostgreSQL 벡터에서 가져온 문서
                        source_id=ref.get("source_id", ""),
                        title=ref.get("title", ""),
                        url=ref.get("url", ""),
                        snippet=ref.get("snippet", ""),
                        score=ref.get("score", 0.0),
                        rank=idx + 1,
                        extra_metadata=ref
                    )
                    rag_refs.append(rag_ref)
                    new_session.add(rag_ref)

                await new_session.commit()
                logger.debug(f"🔗 RAG 참조 저장 - message_id: {message_id}, 참조 수: {len(rag_refs)}")
                return rag_refs
                
            except Exception as e:
                logger.error(f"❌ RAG 참조 저장 실패: {e}")
                try:
                    await new_session.rollback()
                except Exception as rollback_error:
                    logger.error(f"❌ RAG 참조 롤백 실패: {rollback_error}")
                raise

    @staticmethod
    async def update_session_title(
        session: AsyncSession,
        session_id: uuid.UUID,
        user_id: int,
        title: str
    ) -> Optional[ChatSession]:
        """채팅 세션의 제목을 업데이트합니다."""
        chat_session = await ChatRepository.get_session(session, session_id, user_id)
        if chat_session:
            chat_session.title = title
            chat_session.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(chat_session)
            logger.info(f"📝 세션 제목 업데이트 - session_id: {session_id}, title: {title}")
        return chat_session

    @staticmethod
    async def deactivate_session(
        session: AsyncSession,
        session_id: uuid.UUID,
        user_id: int
    ) -> bool:
        """채팅 세션을 비활성화합니다."""
        chat_session = await ChatRepository.get_session(session, session_id, user_id)
        if chat_session:
            chat_session.is_active = False
            chat_session.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"🔇 세션 비활성화 - session_id: {session_id}")
            return True
        return False

    @staticmethod
    async def save_user_feedback(
        session: AsyncSession,
        message_id: uuid.UUID,
        user_id: int,
        feedback_type: str,
        **kwargs
    ) -> UserFeedback:
        """사용자 피드백을 저장합니다."""
        rating = kwargs.get('rating')
        comment = kwargs.get('comment')

        feedback_detail = None
        if comment:
            feedback_detail = {"comment": comment}

        feedback = UserFeedback(
            message_id=message_id,
            user_id=user_id,  # int 형태 그대로 사용
            feedback_type=feedback_type,
            feedback_score=rating or 3,  # 기본값 3
            feedback_detail=feedback_detail
        )
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)

        logger.info(f"👍 피드백 저장 - message_id: {message_id}, type: {feedback_type}")
        return feedback
