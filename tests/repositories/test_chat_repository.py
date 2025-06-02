"""
ChatRepository 테스트

채팅 세션, 메시지, RAG 참조 등 Repository 패턴의 모든 기능을 테스트합니다.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.repositories.chat_repository import ChatRepository
from app.models.chat import ChatSession, ChatMessage, RAGReference


class TestChatRepository:
    """ChatRepository 테스트 클래스"""

    @pytest.mark.asyncio
    async def test_create_session(self, async_session: AsyncSession):
        """새 채팅 세션 생성 테스트"""
        user_id = 12345
        title = "테스트 세션"
        
        session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title=title,
            session_type="test"
        )
        
        assert session.id is not None
        assert session.user_id == str(user_id)
        assert session.title == title
        assert session.session_type == "test"
        assert session.is_active is True
        assert session.total_messages == 0
        assert isinstance(session.created_at, datetime)

    @pytest.mark.asyncio
    async def test_get_session(self, async_session: AsyncSession):
        """세션 조회 테스트"""
        user_id = 12345
        
        # 세션 생성
        created_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="조회 테스트 세션"
        )
        
        # 세션 조회
        retrieved_session = await ChatRepository.get_session(
            session=async_session,
            session_id=created_session.id,
            user_id=user_id
        )
        
        assert retrieved_session is not None
        assert retrieved_session.id == created_session.id
        assert retrieved_session.user_id == str(user_id)
        assert retrieved_session.title == "조회 테스트 세션"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, async_session: AsyncSession):
        """존재하지 않는 세션 조회 테스트"""
        fake_session_id = uuid.uuid4()
        user_id = 12345
        
        session = await ChatRepository.get_session(
            session=async_session,
            session_id=fake_session_id,
            user_id=user_id
        )
        
        assert session is None

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, async_session: AsyncSession):
        """사용자 세션 목록 조회 테스트"""
        user_id = 12345
        
        # 여러 세션 생성
        session1 = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="세션 1"
        )
        session2 = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="세션 2"
        )
        
        # 세션 목록 조회
        sessions = await ChatRepository.get_user_sessions(
            session=async_session,
            user_id=user_id,
            limit=10,
            offset=0
        )
        
        assert len(sessions) >= 2
        session_ids = [str(s.id) for s in sessions]
        assert str(session1.id) in session_ids
        assert str(session2.id) in session_ids

    @pytest.mark.asyncio
    async def test_save_message(self, async_session: AsyncSession):
        """메시지 저장 테스트"""
        user_id = 12345
        
        # 세션 생성
        chat_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="메시지 테스트 세션"
        )
        
        # 사용자 메시지 저장
        user_message = await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content="안녕하세요!",
            role="user",
            user_id=user_id
        )
        
        assert user_message.id is not None
        assert user_message.session_id == chat_session.id
        assert user_message.content == "안녕하세요!"
        assert user_message.role == "user"
        assert user_message.user_id == str(user_id)
        assert isinstance(user_message.created_at, datetime)
        
        # AI 응답 메시지 저장
        ai_metadata = {
            "model": "gpt-3.5-turbo",
            "token_count": 25,
            "response_time_ms": 1500
        }
        
        ai_message = await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content="안녕하세요! 도움이 필요하시면 언제든 말씀해주세요.",
            role="assistant",
            user_id=user_id,
            metadata=ai_metadata
        )
        
        assert ai_message.id is not None
        assert ai_message.role == "assistant"
        assert ai_message.rag_metadata == ai_metadata

    @pytest.mark.asyncio
    async def test_duplicate_message_prevention(self, async_session: AsyncSession):
        """중복 메시지 방지 테스트"""
        user_id = 12345
        
        # 세션 생성
        chat_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="중복 방지 테스트"
        )
        
        message_content = "중복 테스트 메시지"
        
        # 첫 번째 메시지 저장
        message1 = await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content=message_content,
            role="user",
            user_id=user_id
        )
        
        # 같은 내용의 메시지를 즉시 다시 저장 (중복 방지 작동)
        message2 = await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content=message_content,
            role="user",
            user_id=user_id
        )
        
        # 같은 메시지 객체가 반환되어야 함
        assert message1.id == message2.id
        assert message1.content == message2.content

    @pytest.mark.asyncio
    async def test_get_session_messages(self, async_session: AsyncSession):
        """세션 메시지 조회 테스트"""
        user_id = 12345
        
        # 세션 생성
        chat_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="메시지 조회 테스트"
        )
        
        # 여러 메시지 저장
        await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content="첫 번째 메시지",
            role="user",
            user_id=user_id
        )
        
        await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content="두 번째 메시지 (AI 응답)",
            role="assistant",
            user_id=user_id,
            metadata={"model": "gpt-3.5-turbo"}
        )
        
        # 메시지 조회
        messages = await ChatRepository.get_session_messages(
            session=async_session,
            session_id=chat_session.id,
            user_id=user_id
        )
        
        assert len(messages) == 2
        assert messages[0].content == "첫 번째 메시지"
        assert messages[0].role == "user"
        assert messages[1].content == "두 번째 메시지 (AI 응답)"
        assert messages[1].role == "assistant"
        assert messages[1].rag_metadata["model"] == "gpt-3.5-turbo"
        
        # 시간 순서대로 정렬되었는지 확인
        assert messages[0].created_at <= messages[1].created_at

    @pytest.mark.asyncio
    async def test_save_rag_references(self, async_session: AsyncSession):
        """RAG 참조 저장 테스트"""
        user_id = 12345
        
        # 세션 및 메시지 생성
        chat_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="RAG 참조 테스트"
        )
        
        ai_message = await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content="AI 응답",
            role="assistant",
            user_id=user_id
        )
        
        # RAG 참조 데이터
        references = [
            {
                "snippet": "첫 번째 참조 문서 내용",
                "title": "문서 1",
                "url": "https://example.com/doc1",
                "source_id": "doc_1",
                "score": 0.95
            },
            {
                "snippet": "두 번째 참조 문서 내용",
                "title": "문서 2",
                "url": "https://example.com/doc2",
                "source_id": "doc_2",
                "score": 0.87
            }
        ]
        
        # RAG 참조 저장
        rag_refs = await ChatRepository.save_rag_references(
            session=async_session,
            message_id=ai_message.id,
            references=references
        )
        
        assert len(rag_refs) == 2
        assert rag_refs[0].message_id == ai_message.id
        assert rag_refs[0].title == "문서 1"
        assert rag_refs[0].score == 0.95
        assert rag_refs[0].rank == 1
        assert rag_refs[1].rank == 2

    @pytest.mark.asyncio
    async def test_update_session_title(self, async_session: AsyncSession):
        """세션 제목 업데이트 테스트"""
        user_id = 12345
        
        # 세션 생성
        chat_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="원래 제목"
        )
        
        # 제목 업데이트
        new_title = "업데이트된 제목"
        updated_session = await ChatRepository.update_session_title(
            session=async_session,
            session_id=chat_session.id,
            user_id=user_id,
            title=new_title
        )
        
        assert updated_session is not None
        assert updated_session.title == new_title
        assert updated_session.id == chat_session.id

    @pytest.mark.asyncio
    async def test_deactivate_session(self, async_session: AsyncSession):
        """세션 비활성화 테스트"""
        user_id = 12345
        
        # 세션 생성
        chat_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="비활성화 테스트"
        )
        
        assert chat_session.is_active is True
        
        # 세션 비활성화
        result = await ChatRepository.deactivate_session(
            session=async_session,
            session_id=chat_session.id,
            user_id=user_id
        )
        
        assert result is True
        
        # 세션 다시 조회하여 비활성화 확인
        deactivated_session = await ChatRepository.get_session(
            session=async_session,
            session_id=chat_session.id,
            user_id=user_id
        )
        
        assert deactivated_session.is_active is False

    @pytest.mark.asyncio
    async def test_save_user_feedback(self, async_session: AsyncSession):
        """사용자 피드백 저장 테스트"""
        user_id = 12345
        
        # 세션 및 메시지 생성
        chat_session = await ChatRepository.create_session(
            session=async_session,
            user_id=user_id,
            title="피드백 테스트"
        )
        
        ai_message = await ChatRepository.save_message(
            session=async_session,
            session_id=chat_session.id,
            content="AI 응답",
            role="assistant",
            user_id=user_id
        )
        
        # 피드백 저장
        feedback = await ChatRepository.save_user_feedback(
            session=async_session,
            message_id=ai_message.id,
            user_id=user_id,
            feedback_type="helpful",
            rating=5,
            comment="매우 도움이 되었습니다"
        )
        
        assert feedback.id is not None
        assert feedback.message_id == ai_message.id
        assert feedback.user_id == str(user_id)
        assert feedback.feedback_type == "helpful"
        assert feedback.feedback_score == 5
        assert feedback.feedback_detail["comment"] == "매우 도움이 되었습니다" 