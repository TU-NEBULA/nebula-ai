"""
북마크 요약 API 테스트

북마크 요약 라우터의 기본 동작을 테스트합니다.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

client = TestClient(app)

class TestBookmarkSummaryRoutes:
    """북마크 요약 라우터 테스트"""

    def test_summarize_bookmark_stream_validation(self):
        """요약 스트리밍 입력 검증 테스트 (url/s3_key)"""
        # url, s3_key 모두 없음
        response = client.post(
            "/bookmark/summary/stream",
            params={
                "user_id": 1
            }
        )
        assert response.status_code == 400
        assert "url 또는 s3_key" in response.json()["detail"]

        # 잘못된 language
        response = client.post(
            "/bookmark/summary/stream",
            params={
                "user_id": 1,
                "url": "https://example.com",
                "language": "invalid_lang"
            }
        )
        assert response.status_code == 400
        assert "language" in response.json()["detail"]

        # 잘못된 max_length (너무 작음)
        response = client.post(
            "/bookmark/summary/stream",
            params={
                "user_id": 1,
                "url": "https://example.com",
                "max_length": 10
            }
        )
        assert response.status_code == 400
        assert "max_length" in response.json()["detail"]

        # 잘못된 max_length (너무 큼)
        response = client.post(
            "/bookmark/summary/stream",
            params={
                "user_id": 1,
                "url": "https://example.com",
                "max_length": 5000
            }
        )
        assert response.status_code == 400
        assert "max_length" in response.json()["detail"]

    @patch('app.services.bookmark_summary_service.BookmarkSummaryService.generate_summary_stream')
    def test_summarize_bookmark_stream_success_url(self, mock_generate_stream):
        """url 기반 요약 스트리밍 성공 테스트"""
        async def mock_stream():
            yield "event: progress\ndata: {\"step\": \"extracting_content\", \"progress\": 10, \"message\": \"본문을 추출하고 있습니다...\"}\n\n"
            yield "event: complete\ndata: {\"url\": \"https://example.com\", \"summary\": \"테스트 요약\"}\n\n"
            yield "event: end\ndata: {}\n\n"
        mock_generate_stream.return_value = mock_stream()
        response = client.post(
            "/bookmark/summary/stream",
            params={
                "user_id": 1,
                "url": "https://example.com"
            }
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @patch('app.services.bookmark_summary_service.BookmarkSummaryService.generate_summary_stream')
    def test_summarize_bookmark_stream_success_s3(self, mock_generate_stream):
        """s3_key 기반 요약 스트리밍 성공 테스트"""
        async def mock_stream():
            yield "event: progress\ndata: {\"step\": \"extracting_content\", \"progress\": 10, \"message\": \"본문을 추출하고 있습니다...\"}\n\n"
            yield "event: complete\ndata: {\"s3_key\": \"test-key\", \"summary\": \"테스트 요약\"}\n\n"
            yield "event: end\ndata: {}\n\n"
        mock_generate_stream.return_value = mock_stream()
        response = client.post(
            "/bookmark/summary/stream",
            params={
                "user_id": 1,
                "s3_key": "test-key"
            }
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @patch('app.repositories.vector_repository.VectorRepository.get_documents_by_user')
    def test_get_user_bookmarks(self, mock_get_documents):
        """사용자 북마크 목록 조회 테스트"""
        from app.models.chat import DocumentVector
        from datetime import datetime

        # Mock 데이터
        mock_documents = [
            DocumentVector(
                id="1",
                user_id=1,
                source_id="bookmark1",
                source_type="bookmark",
                chunk_index=0,
                content="Test content 1",
                embedding=[0.1, 0.2, 0.3],
                title="Test Bookmark 1",
                url="https://example.com/1",
                keywords=["test", "example"],
                created_at=datetime.now()
            ),
            DocumentVector(
                id="2",
                user_id=1,
                source_id="bookmark2",
                source_type="bookmark",
                chunk_index=0,
                content="Test content 2",
                embedding=[0.4, 0.5, 0.6],
                title="Test Bookmark 2",
                url="https://example.com/2",
                keywords=["test2", "example2"],
                created_at=datetime.now()
            )
        ]

        mock_get_documents.return_value = mock_documents

        response = client.get("/bookmark/user/1/bookmarks")

        assert response.status_code == 200
        data = response.json()

        assert "bookmarks" in data
        assert "total_count" in data
        assert "offset" in data
        assert "limit" in data
        assert "has_more" in data

        assert len(data["bookmarks"]) == 2
        assert data["total_count"] == 2

    def test_get_user_bookmarks_pagination(self):
        """사용자 북마크 목록 페이지네이션 테스트"""
        response = client.get("/bookmark/user/1/bookmarks?limit=5&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert "bookmarks" in data
        assert data["offset"] == 10
        assert data["limit"] == 5 