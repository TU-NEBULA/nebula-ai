"""
채팅 Repository

채팅 세션, 메시지, RAG 메타데이터에 대한 데이터 접근을 담당합니다.
Repository 패턴을 통해 데이터베이스 로직을 캡슐화합니다.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlmodel import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import (
    ChatSession, ChatMessage, RAGReference, UserFeedback
)
from loguru import logger


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
        chat_session = ChatSession(
            user_id=str(user_id),  # 스키마에 맞게 문자열로 변환
            title=title or "새로운 대화",
            session_type=session_type,
            is_active=True
        )
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)
        
        logger.info(f"📝 새 채팅 세션 생성 - session_id: {chat_session.id}, user_id: {user_id}")
        return chat_session
    
    @staticmethod
    async def get_session(
        session: AsyncSession,
        session_id: uuid.UUID,
        user_id: int
    ) -> Optional[ChatSession]:
        """특정 채팅 세션을 조회합니다."""
        stmt = select(ChatSession).where(
            and_(
                ChatSession.id == session_id,
                ChatSession.user_id == str(user_id)
            )
        )
        result = await session.exec(stmt)
        return result.first()
    
    @staticmethod
    async def get_user_sessions(
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatSession]:
        """사용자의 채팅 세션 목록을 조회합니다."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == str(user_id))
            .order_by(ChatSession.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(stmt)
        return list(result.all())
    
    @staticmethod
    async def save_message(
        session: AsyncSession,
        session_id: uuid.UUID,
        content: str,
        role: str,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """채팅 메시지를 저장합니다."""
        message = ChatMessage(
            session_id=session_id,
            content=content,
            role=role,
            user_id=str(user_id),
            rag_metadata=metadata or {}
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        
        logger.debug(f"💾 메시지 저장 - session_id: {session_id}, role: {role}")
        return message
    
    @staticmethod
    async def get_session_messages(
        session: AsyncSession,
        session_id: uuid.UUID,
        user_id: int,
        limit: int = 100
    ) -> List[ChatMessage]:
        """채팅 세션의 메시지 목록을 조회합니다."""
        stmt = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.session_id == session_id,
                    ChatMessage.user_id == str(user_id)
                )
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await session.exec(stmt)
        return list(result.all())
    
    @staticmethod
    async def save_rag_references(
        session: AsyncSession,
        message_id: uuid.UUID,
        references: List[Dict[str, Any]]
    ) -> List[RAGReference]:
        """RAG 참조 문서들을 저장합니다."""
        rag_refs = []
        for idx, ref in enumerate(references):
            rag_ref = RAGReference(
                message_id=message_id,
                source_type="chroma",  # ChromaDB에서 가져온 문서
                source_id=ref.get("source_id", ""),
                title=ref.get("title", ""),
                url=ref.get("url", ""),
                snippet=ref.get("snippet", ""),
                score=ref.get("score", 0.0),
                rank=idx + 1,
                extra_metadata=ref
            )
            rag_refs.append(rag_ref)
            session.add(rag_ref)
        
        await session.commit()
        logger.debug(f"🔗 RAG 참조 저장 - message_id: {message_id}, 참조 수: {len(rag_refs)}")
        return rag_refs
    
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
            chat_session.updated_at = datetime.utcnow()
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
            chat_session.updated_at = datetime.utcnow()
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
        rating: Optional[int] = None,
        comment: Optional[str] = None
    ) -> UserFeedback:
        """사용자 피드백을 저장합니다."""
        feedback_detail = None
        if comment:
            feedback_detail = {"comment": comment}
            
        feedback = UserFeedback(
            message_id=message_id,
            user_id=str(user_id),
            feedback_type=feedback_type,
            feedback_score=rating or 3,  # 기본값 3
            feedback_detail=feedback_detail
        )
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)
        
        logger.info(f"👍 피드백 저장 - message_id: {message_id}, type: {feedback_type}")
        return feedback 
