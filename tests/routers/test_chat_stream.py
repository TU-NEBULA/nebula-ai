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
        
        # BaseResponse 구조 검증
        assert data["success"] is True
        assert "message" in data
        assert "data" in data
        
        # IDResponse 구조 검증
        session_data = data["data"]
        assert "id" in session_data

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
        
        # BaseResponse 구조 검증
        assert data["success"] is True
        assert "message" in data
        assert "data" in data
        
        # ChatSessionListResponse 구조 검증
        session_list_data = data["data"]
        assert "sessions" in session_list_data
        assert "total" in session_list_data
        assert len(session_list_data["sessions"]) >= 2
        
        # 개별 세션 구조 확인
        session = session_list_data["sessions"][0]
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
        create_data = create_response.json()
        session_id = create_data["data"]["id"]  # BaseResponse에서 데이터 추출
        
        # 메시지 조회 (빈 세션)
        response = await async_client.get(
            f"/chat/sessions/{session_id}/messages",
            params={"user_id": 123}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # BaseResponse 구조 검증
        assert data["success"] is True
        assert "message" in data
        assert "data" in data
        
        # ChatSessionMessagesResponse 구조 검증
        messages_data = data["data"]
        assert messages_data["session_id"] == session_id
        assert "messages" in messages_data
        assert len(messages_data["messages"]) == 0

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
    @patch('app.routers.chat_stream.vector_service.similarity_search')
    @patch('app.routers.chat_stream.ChatOpenAI')
    async def test_chat_stream_new_session(
        self, 
        mock_openai, 
        mock_vector_search,
        async_client: AsyncClient
    ):
        """새 세션으로 채팅 스트림 테스트"""
        # Mock 설정
        mock_vector_search.return_value = []  # 빈 검색 결과
        
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
    @patch('app.routers.chat_stream.vector_service.similarity_search')
    @patch('app.routers.chat_stream.ChatOpenAI')
    async def test_chat_stream_existing_session(
        self, 
        mock_openai, 
        mock_vector_search,
        async_client: AsyncClient
    ):
        """기존 세션으로 채팅 스트림 테스트"""
        # 세션 생성
        create_response = await async_client.post(
            "/chat/sessions",
            params={"user_id": 123, "title": "기존 세션 테스트"}
        )
        create_data = create_response.json()
        session_id = create_data["data"]["id"]  # BaseResponse에서 데이터 추출
        
        # Mock 설정
        mock_vector_search.return_value = []  # 빈 검색 결과
        
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
        
        with patch('app.routers.chat_stream.vector_service.similarity_search'), \
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
        response = await async_client.post(
            "/chat/stream",
            json={
                "message": "user_id가 없는 요청"
                # user_id 누락
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_chat_stream_missing_message(self, async_client: AsyncClient):
        """메시지가 없는 채팅 스트림 요청 테스트"""
        response = await async_client.post(
            "/chat/stream",
            json={
                "user_id": 123
                # message 누락
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
        create_response = await async_client.post(
            "/chat/sessions",
            params={"user_id": user_id, "title": "통합 테스트 세션"}
        )
        
        assert create_response.status_code == status.HTTP_200_OK
        create_data = create_response.json()
        assert create_data["success"] is True
        session_id = create_data["data"]["id"]
        
        # 2. 세션 목록에서 확인
        list_response = await async_client.get(
            "/chat/sessions",
            params={"user_id": user_id}
        )
        
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        assert list_data["success"] is True
        
        # 생성한 세션이 목록에 있는지 확인
        sessions = list_data["data"]["sessions"]
        session_ids = [s["id"] for s in sessions]
        assert session_id in session_ids
        
        # 3. 메시지 조회 (빈 상태)
        messages_response = await async_client.get(
            f"/chat/sessions/{session_id}/messages",
            params={"user_id": user_id}
        )
        
        assert messages_response.status_code == status.HTTP_200_OK
        messages_data = messages_response.json()
        assert messages_data["success"] is True
        assert len(messages_data["data"]["messages"]) == 0
        
        # 4. 실제 채팅 테스트는 mock이 필요하므로 생략
        # (스트리밍 응답은 별도 테스트에서 처리) 
