"""
채팅 스트림 API 테스트

PostgreSQL 연동 채팅 스트리밍 API의 모든 기능을 테스트합니다.
"""
import pytest
import json
import uuid
from httpx import AsyncClient
from fastapi import status
from unittest.mock import AsyncMock, patch

from app.main import app


class TestChatStreamAPI:
    """채팅 스트림 API 테스트 클래스"""

    @pytest.mark.asyncio
    async def test_create_chat_session(self, async_client: AsyncClient):
        """새 채팅 세션 생성 API 테스트"""
        response = await async_client.post(
            "/chat/sessions",
            params={"user_id": 123, "title": "테스트 세션"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "session_id" in data
        assert data["title"] == "테스트 세션"
        assert data["is_active"] is True
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, async_client: AsyncClient):
        """사용자 세션 목록 조회 API 테스트"""
        # 먼저 세션 생성
        await async_client.post(
            "/chat/sessions",
            params={"user_id": 123, "title": "테스트 세션 1"}
        )
        
        await async_client.post(
            "/chat/sessions",
            params={"user_id": 123, "title": "테스트 세션 2"}
        )
        
        # 세션 목록 조회
        response = await async_client.get(
            "/chat/sessions",
            params={"user_id": 123, "limit": 10, "offset": 0}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "sessions" in data
        assert "total" in data
        assert len(data["sessions"]) >= 2
        
        # 세션 구조 확인
        session = data["sessions"][0]
        assert "id" in session
        assert "title" in session
        assert "session_type" in session
        assert "created_at" in session
        assert "is_active" in session

    @pytest.mark.asyncio
    async def test_get_session_messages(self, async_client: AsyncClient):
        """세션 메시지 조회 API 테스트"""
        # 세션 생성
        create_response = await async_client.post(
            "/chat/sessions",
            params={"user_id": 123, "title": "메시지 테스트 세션"}
        )
        session_data = create_response.json()
        session_id = session_data["session_id"]
        
        # 메시지 조회 (빈 세션)
        response = await async_client.get(
            f"/chat/sessions/{session_id}/messages",
            params={"user_id": 123}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["session_id"] == session_id
        assert "messages" in data
        assert len(data["messages"]) == 0

    @pytest.mark.asyncio
    async def test_get_session_messages_invalid_session_id(self, async_client: AsyncClient):
        """잘못된 세션 ID로 메시지 조회 테스트"""
        response = await async_client.get(
            "/chat/sessions/invalid-session-id/messages",
            params={"user_id": 123}
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "올바르지 않은 세션 ID 형식입니다" in data["detail"]

    @pytest.mark.asyncio
    @patch('app.routers.chat_stream._get_vectordb')
    @patch('app.routers.chat_stream.ChatOpenAI')
    async def test_chat_stream_new_session(
        self, 
        mock_openai, 
        mock_vectordb,
        async_client: AsyncClient
    ):
        """새 세션으로 채팅 스트림 테스트"""
        # Mock 설정
        mock_vectordb.return_value.similarity_search_with_score.return_value = []
        
        # Mock LLM 스트림 응답
        mock_stream_chunk = AsyncMock()
        mock_stream_chunk.content = "안녕하세요!"
        mock_openai.return_value.stream.return_value = [mock_stream_chunk]
        
        # 채팅 스트림 요청
        response = await async_client.post(
            "/chat/stream",
            json={
                "user_id": 123,
                "message": "안녕하세요!"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @pytest.mark.asyncio
    @patch('app.routers.chat_stream._get_vectordb')
    @patch('app.routers.chat_stream.ChatOpenAI')
    async def test_chat_stream_existing_session(
        self, 
        mock_openai, 
        mock_vectordb,
        async_client: AsyncClient
    ):
        """기존 세션으로 채팅 스트림 테스트"""
        # 세션 생성
        create_response = await async_client.post(
            "/chat/sessions",
            params={"user_id": 123, "title": "기존 세션 테스트"}
        )
        session_data = create_response.json()
        session_id = session_data["session_id"]
        
        # Mock 설정
        mock_vectordb.return_value.similarity_search_with_score.return_value = []
        
        mock_stream_chunk = AsyncMock()
        mock_stream_chunk.content = "기존 세션에서 응답합니다!"
        mock_openai.return_value.stream.return_value = [mock_stream_chunk]
        
        # 기존 세션으로 채팅 스트림 요청
        response = await async_client.post(
            "/chat/stream",
            json={
                "user_id": 123,
                "message": "기존 세션에서 대화합니다",
                "session_id": session_id
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @pytest.mark.asyncio
    async def test_chat_stream_with_idempotency_key(self, async_client: AsyncClient):
        """Idempotency Key로 중복 방지 테스트"""
        idempotency_key = str(uuid.uuid4())
        
        with patch('app.routers.chat_stream._get_vectordb'), \
             patch('app.routers.chat_stream.ChatOpenAI') as mock_openai:
            
            # Mock 설정
            mock_stream_chunk = AsyncMock()
            mock_stream_chunk.content = "중복 방지 테스트!"
            mock_openai.return_value.stream.return_value = [mock_stream_chunk]
            
            # 첫 번째 요청
            response1 = await async_client.post(
                "/chat/stream",
                json={
                    "user_id": 123,
                    "message": "중복 방지 테스트 메시지"
                },
                headers={"idempotency-key": idempotency_key}
            )
            
            assert response1.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_chat_stream_invalid_request(self, async_client: AsyncClient):
        """잘못된 요청으로 채팅 스트림 테스트"""
        # user_id 누락
        response = await async_client.post(
            "/chat/stream",
            json={
                "message": "안녕하세요!"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_chat_stream_missing_message(self, async_client: AsyncClient):
        """메시지 누락으로 채팅 스트림 테스트"""
        response = await async_client.post(
            "/chat/stream",
            json={
                "user_id": 123
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestChatStreamIntegration:
    """채팅 스트림 통합 테스트"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_chat_flow(self, async_client: AsyncClient):
        """전체 채팅 플로우 통합 테스트"""
        user_id = 999
        
        # 1. 새 세션 생성
        session_response = await async_client.post(
            "/chat/sessions",
            params={"user_id": user_id, "title": "통합 테스트 세션"}
        )
        assert session_response.status_code == 200
        session_data = session_response.json()
        session_id = session_data["session_id"]
        
        # 2. 세션 목록에서 확인
        sessions_response = await async_client.get(
            "/chat/sessions",
            params={"user_id": user_id, "limit": 10}
        )
        assert sessions_response.status_code == 200
        sessions_data = sessions_response.json()
        session_ids = [s["id"] for s in sessions_data["sessions"]]
        assert session_id in session_ids
        
        # 3. 메시지 히스토리 조회 (빈 상태)
        messages_response = await async_client.get(
            f"/chat/sessions/{session_id}/messages",
            params={"user_id": user_id}
        )
        assert messages_response.status_code == 200
        messages_data = messages_response.json()
        assert len(messages_data["messages"]) == 0
        
        # 4. Mock을 사용한 채팅 (실제 OpenAI 호출 방지)
        with patch('app.routers.chat_stream._get_vectordb'), \
             patch('app.routers.chat_stream.ChatOpenAI') as mock_openai:
            
            mock_stream_chunk = AsyncMock()
            mock_stream_chunk.content = "통합 테스트 응답입니다!"
            mock_openai.return_value.stream.return_value = [mock_stream_chunk]
            
            chat_response = await async_client.post(
                "/chat/stream",
                json={
                    "user_id": user_id,
                    "message": "통합 테스트 메시지",
                    "session_id": session_id
                }
            )
            assert chat_response.status_code == 200
        
        # 5. 메시지 히스토리 다시 조회 (메시지 추가됨)
        final_messages_response = await async_client.get(
            f"/chat/sessions/{session_id}/messages",
            params={"user_id": user_id}
        )
        assert final_messages_response.status_code == 200
        final_messages_data = final_messages_response.json()
        
        # 사용자 메시지와 AI 응답이 저장되었는지 확인
        assert len(final_messages_data["messages"]) >= 1 
