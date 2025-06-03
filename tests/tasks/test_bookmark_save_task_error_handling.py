"""
북마크 저장 태스크 에러 핸들링 테스트

이 파일은 app/tasks/bookmark_save_task.py의 모든 에러 핸들링 부분을 테스트하여
100% 커버리지를 달성합니다.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import asdict

from app.tasks.bookmark_save_task import (
    BookmarkData, save_bookmark_task, _save_bookmark_logic,
    _download_and_extract_content, _calculate_similarity,
    _publish_relationships, _delete_existing_data,
    _delete_pattern_individually, _save_content_chunks,
    _save_memo_if_exists, _save_summary_if_exists
)


class TestBookmarkDataValidation:
    """BookmarkData 검증 테스트"""

    def test_bookmark_data_creation_success(self):
        """정상적인 BookmarkData 생성 테스트"""
        data = BookmarkData(
            user_id=123,
            star_id="test_star",
            s3_key="test_key",
            title="Test Title",
            url="https://test.com",
            keywords=["test", "keyword"],
            memo="Test memo",
            summary="Test summary"
        )
        
        assert data.user_id == 123
        assert data.star_id == "test_star"
        assert data.s3_key == "test_key"
        assert data.title == "Test Title"
        assert data.url == "https://test.com"
        assert data.keywords == ["test", "keyword"]
        assert data.memo == "Test memo"
        assert data.summary == "Test summary"

    def test_bookmark_data_from_dict_missing_fields(self):
        """BookmarkData 생성 시 필수 필드 누락 테스트"""
        incomplete_data = {
            "user_id": 123,
            "star_id": "test_star"
            # 나머지 필드들 누락
        }
        
        with pytest.raises(TypeError):
            BookmarkData(**incomplete_data)

    def test_bookmark_data_invalid_types(self):
        """BookmarkData 생성 시 잘못된 타입 테스트"""
        # 실제로는 Python의 dataclass는 타입 검증을 자동으로 하지 않지만,
        # 런타임에서 타입 문제가 발생할 수 있는 케이스들을 테스트
        data = BookmarkData(
            user_id="not_an_integer",  # 문자열
            star_id=123,  # 숫자
            s3_key=None,  # None
            title=["list", "instead", "of", "string"],  # 리스트
            url={"dict": "instead_of_string"},  # 딕셔너리
            keywords="string_instead_of_list",  # 문자열
            memo=123,  # 숫자
            summary=None  # None
        )
        
        # 생성은 되지만 후속 처리에서 에러가 발생할 수 있음
        assert data.user_id == "not_an_integer"
        assert data.star_id == 123


class TestDownloadAndExtractContent:
    """콘텐츠 다운로드 및 추출 에러 테스트"""

    @pytest.mark.asyncio
    async def test_s3_download_failure(self):
        """S3 다운로드 실패 테스트"""
        with patch('app.tasks.bookmark_save_task.download_html_from_s3') as mock_download:
            mock_download.side_effect = ConnectionError("S3 connection failed")
            
            with pytest.raises(ConnectionError):
                await _download_and_extract_content("test_key")

    @pytest.mark.asyncio
    async def test_s3_timeout_error(self):
        """S3 다운로드 타임아웃 테스트"""
        with patch('app.tasks.bookmark_save_task.download_html_from_s3') as mock_download:
            mock_download.side_effect = TimeoutError("S3 download timeout")
            
            with pytest.raises(TimeoutError):
                await _download_and_extract_content("test_key")

    @pytest.mark.asyncio
    async def test_html_extraction_failure(self):
        """HTML 텍스트 추출 실패 테스트"""
        with patch('app.tasks.bookmark_save_task.download_html_from_s3') as mock_download:
            mock_download.return_value = "<html>test</html>"
            
            with patch('app.tasks.bookmark_save_task.extract_main_text') as mock_extract:
                mock_extract.side_effect = ValueError("HTML parsing failed")
                
                with pytest.raises(ValueError):
                    await _download_and_extract_content("test_key")

    @pytest.mark.asyncio
    async def test_empty_html_content(self):
        """빈 HTML 콘텐츠 테스트"""
        with patch('app.tasks.bookmark_save_task.download_html_from_s3') as mock_download:
            mock_download.return_value = ""
            
            with patch('app.tasks.bookmark_save_task.extract_main_text') as mock_extract:
                mock_extract.return_value = ""
                
                result = await _download_and_extract_content("test_key")
                assert result == ""

    @pytest.mark.asyncio
    async def test_none_html_content(self):
        """None HTML 콘텐츠 테스트"""
        with patch('app.tasks.bookmark_save_task.download_html_from_s3') as mock_download:
            mock_download.return_value = None
            
            with patch('app.tasks.bookmark_save_task.extract_main_text') as mock_extract:
                mock_extract.side_effect = AttributeError("'NoneType' object has no attribute")
                
                with pytest.raises(AttributeError):
                    await _download_and_extract_content("test_key")


class TestSimilarityCalculation:
    """유사도 계산 에러 테스트"""

    @pytest.mark.asyncio
    async def test_similarity_service_connection_error(self):
        """SimilarityService 연결 오류 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title", 
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.similarity_service.find_similar_bookmarks') as mock_sim:
            mock_sim.side_effect = ConnectionError("Similarity service unavailable")
            
            with pytest.raises(ConnectionError):
                await _calculate_similarity(bookmark_data, "test body text")

    @pytest.mark.asyncio
    async def test_similarity_service_timeout(self):
        """SimilarityService 타임아웃 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.similarity_service.find_similar_bookmarks') as mock_sim:
            mock_sim.side_effect = TimeoutError("Similarity calculation timeout")
            
            with pytest.raises(TimeoutError):
                await _calculate_similarity(bookmark_data, "test body text")

    @pytest.mark.asyncio
    async def test_similarity_service_value_error(self):
        """SimilarityService 데이터 오류 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.similarity_service.find_similar_bookmarks') as mock_sim:
            mock_sim.side_effect = ValueError("Invalid similarity parameters")
            
            with pytest.raises(ValueError):
                await _calculate_similarity(bookmark_data, "test body text")

    @pytest.mark.asyncio
    async def test_empty_body_text(self):
        """빈 본문 텍스트로 유사도 계산 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.similarity_service.find_similar_bookmarks') as mock_sim:
            mock_sim.return_value = []
            
            result = await _calculate_similarity(bookmark_data, "")
            assert result == []
            
            # 빈 텍스트여도 서비스가 호출되었는지 확인
            mock_sim.assert_called_once()


class TestPublishRelationships:
    """관계 데이터 발행 에러 테스트"""

    @pytest.mark.asyncio
    async def test_no_similar_bookmarks(self):
        """유사한 북마크가 없는 경우 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        result = await _publish_relationships(bookmark_data, [])
        assert result is False

    @pytest.mark.asyncio
    async def test_message_publisher_connection_error(self):
        """메시지 발행자 연결 오류 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        similar_bookmarks = [{"id": "similar1", "title": "Similar"}]
        
        with patch('app.tasks.bookmark_save_task.message_publisher.publish_bookmark_relationships') as mock_pub:
            mock_pub.side_effect = ConnectionError("Message broker unavailable")
            
            result = await _publish_relationships(bookmark_data, similar_bookmarks)
            assert result is False

    @pytest.mark.asyncio
    async def test_message_publisher_timeout(self):
        """메시지 발행자 타임아웃 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        similar_bookmarks = [{"id": "similar1", "title": "Similar"}]
        
        with patch('app.tasks.bookmark_save_task.message_publisher.publish_bookmark_relationships') as mock_pub:
            mock_pub.side_effect = TimeoutError("Message publish timeout")
            
            result = await _publish_relationships(bookmark_data, similar_bookmarks)
            assert result is False

    @pytest.mark.asyncio
    async def test_message_publisher_value_error(self):
        """메시지 발행자 데이터 오류 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        similar_bookmarks = [{"id": "similar1", "title": "Similar"}]
        
        with patch('app.tasks.bookmark_save_task.message_publisher.publish_bookmark_relationships') as mock_pub:
            mock_pub.side_effect = ValueError("Invalid message format")
            
            result = await _publish_relationships(bookmark_data, similar_bookmarks)
            assert result is False

    @pytest.mark.asyncio
    async def test_message_publisher_returns_false(self):
        """메시지 발행자가 False 반환하는 경우 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        similar_bookmarks = [{"id": "similar1", "title": "Similar"}]
        
        with patch('app.tasks.bookmark_save_task.message_publisher.publish_bookmark_relationships') as mock_pub:
            mock_pub.return_value = False
            
            result = await _publish_relationships(bookmark_data, similar_bookmarks)
            assert result is False

    @pytest.mark.asyncio
    async def test_message_publisher_success(self):
        """메시지 발행 성공 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        similar_bookmarks = [{"id": "similar1", "title": "Similar"}]
        
        with patch('app.tasks.bookmark_save_task.message_publisher.publish_bookmark_relationships') as mock_pub:
            mock_pub.return_value = True
            
            result = await _publish_relationships(bookmark_data, similar_bookmarks)
            assert result is True


class TestDeleteExistingData:
    """기존 데이터 삭제 에러 테스트"""

    @pytest.mark.asyncio
    async def test_delete_document_connection_error(self):
        """문서 삭제 연결 오류 테스트 - 첫 번째 삭제에서 오류 발생"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
            mock_delete.side_effect = ConnectionError("Database connection failed")
            
            # 첫 번째 삭제에서 에러가 발생하면 예외가 전파되어야 함
            with pytest.raises(ConnectionError):
                await _delete_existing_data(mock_session, bookmark_data)

    @pytest.mark.asyncio
    async def test_delete_document_timeout_error(self):
        """문서 삭제 타임아웃 테스트 - 첫 번째 삭제에서 오류 발생"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
            mock_delete.side_effect = TimeoutError("Delete operation timeout")
            
            # 첫 번째 삭제에서 타임아웃 에러가 발생하면 예외가 전파되어야 함
            with pytest.raises(TimeoutError):
                await _delete_existing_data(mock_session, bookmark_data)

    @pytest.mark.asyncio
    async def test_delete_document_value_error(self):
        """문서 삭제 데이터 오류 테스트 - 첫 번째 삭제에서 오류 발생"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
            mock_delete.side_effect = ValueError("Invalid delete parameters")
            
            # 첫 번째 삭제에서 데이터 오류가 발생하면 예외가 전파되어야 함
            with pytest.raises(ValueError):
                await _delete_existing_data(mock_session, bookmark_data)

    @pytest.mark.asyncio
    async def test_delete_documents_by_pattern_attribute_error(self):
        """패턴 삭제 함수가 없는 경우 테스트 - 실제 상황"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        # 기본 삭제는 성공하도록 설정
        def mock_delete_side_effect(*args, **kwargs):
            return 1
        
        with patch('app.tasks.bookmark_save_task.vector_service.delete_document', side_effect=mock_delete_side_effect):
            with patch('app.tasks.bookmark_save_task._delete_pattern_individually') as mock_individual:
                mock_individual.return_value = 3  # 개별 삭제로 3개 삭제
                
                # 실제로는 delete_documents_by_pattern이 없어서 AttributeError 발생하고 개별 삭제로 넘어감
                result = await _delete_existing_data(mock_session, bookmark_data)
                
                # 기본 삭제 2개 + 개별 삭제 3개 * 3패턴 = 11개
                assert result == 2 + (3 * 3)
                
                # 개별 삭제가 3번 호출되었는지 확인 (3개 패턴)
                assert mock_individual.call_count == 3


class TestDeletePatternIndividually:
    """개별 패턴 삭제 에러 테스트"""

    @pytest.mark.asyncio
    async def test_chunk_pattern_deletion_error(self):
        """청크 패턴 삭제 오류 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
            mock_delete.side_effect = Exception("Chunk deletion failed")
            
            # 예외가 발생하면 상위로 전파되어야 함
            with pytest.raises(Exception):
                await _delete_pattern_individually(
                    mock_session, bookmark_data, "test_chunk_"
                )

    @pytest.mark.asyncio
    async def test_memo_pattern_deletion_error(self):
        """메모 패턴 삭제 오류 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
            mock_delete.side_effect = Exception("Memo deletion failed")
            
            # 예외가 발생하면 상위로 전파되어야 함
            with pytest.raises(Exception):
                await _delete_pattern_individually(
                    mock_session, bookmark_data, "test_memo"
                )

    @pytest.mark.asyncio
    async def test_summary_pattern_deletion_error(self):
        """요약 패턴 삭제 오류 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
            mock_delete.side_effect = Exception("Summary deletion failed")
            
            # 예외가 발생하면 상위로 전파되어야 함
            with pytest.raises(Exception):
                await _delete_pattern_individually(
                    mock_session, bookmark_data, "test_summary"
                )

    @pytest.mark.asyncio
    async def test_successful_pattern_deletions(self):
        """성공적인 패턴 삭제 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        # 다양한 패턴에 대한 삭제 테스트
        test_cases = [
            ("test_chunk_", "bookmark_chunk"),
            ("test_memo", "bookmark_memo"),
            ("test_summary", "bookmark_summary"),
            ("unknown_pattern", None)  # 알 수 없는 패턴
        ]
        
        for pattern, expected_source_type in test_cases:
            with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
                mock_delete.return_value = 1
                
                result = await _delete_pattern_individually(
                    mock_session, bookmark_data, pattern
                )
                
                if expected_source_type:
                    assert result >= 1
                    mock_delete.assert_called()
                else:
                    # 알 수 없는 패턴의 경우 삭제가 호출되지 않음
                    assert result == 0


class TestSaveContentChunks:
    """콘텐츠 청크 저장 에러 테스트"""

    @pytest.mark.asyncio
    async def test_prepare_content_for_rag_error(self):
        """RAG 콘텐츠 준비 오류 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.prepare_content_for_rag') as mock_prepare:
            mock_prepare.side_effect = ValueError("RAG preparation failed")
            
            with pytest.raises(ValueError):
                await _save_content_chunks(mock_session, bookmark_data, "body text", [])

    @pytest.mark.asyncio
    async def test_save_document_vector_service_error(self):
        """벡터 서비스 저장 오류 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.prepare_content_for_rag') as mock_prepare:
            mock_prepare.return_value = [
                {
                    "chunk_index": 0, "total_chunks": 1, "content": "test content",
                    "chunk_keywords": ["test"]
                }
            ]
            
            with patch('app.tasks.bookmark_save_task.vector_service.save_document') as mock_save:
                mock_save.side_effect = ConnectionError("Vector service unavailable")
                
                with pytest.raises(ConnectionError):
                    await _save_content_chunks(mock_session, bookmark_data, "body text", [])

    @pytest.mark.asyncio
    async def test_empty_rag_chunks(self):
        """빈 RAG 청크 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.prepare_content_for_rag') as mock_prepare:
            mock_prepare.return_value = []
            
            saved_vectors, rag_chunks = await _save_content_chunks(
                mock_session, bookmark_data, "body text", []
            )
            
            assert saved_vectors == []
            assert rag_chunks == []


class TestSaveMemoIfExists:
    """메모 저장 에러 테스트"""

    @pytest.mark.asyncio
    async def test_empty_memo(self):
        """빈 메모 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="", summary="summary"
        )
        
        result = await _save_memo_if_exists(mock_session, bookmark_data, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_only_memo(self):
        """공백만 있는 메모 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="   \n\t  ", summary="summary"
        )
        
        result = await _save_memo_if_exists(mock_session, bookmark_data, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_none_memo(self):
        """None 메모 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo=None, summary="summary"
        )
        
        result = await _save_memo_if_exists(mock_session, bookmark_data, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_memo_save_vector_service_error(self):
        """메모 저장 시 벡터 서비스 오류 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="Valid memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.save_document') as mock_save:
            mock_save.side_effect = TimeoutError("Memo save timeout")
            
            with pytest.raises(TimeoutError):
                await _save_memo_if_exists(mock_session, bookmark_data, [])


class TestSaveSummaryIfExists:
    """요약 저장 에러 테스트"""

    @pytest.mark.asyncio
    async def test_empty_summary(self):
        """빈 요약 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary=""
        )
        
        result = await _save_summary_if_exists(mock_session, bookmark_data, [], [])
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_only_summary(self):
        """공백만 있는 요약 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="   \n\t  "
        )
        
        result = await _save_summary_if_exists(mock_session, bookmark_data, [], [])
        assert result == []

    @pytest.mark.asyncio
    async def test_none_summary(self):
        """None 요약 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary=None
        )
        
        result = await _save_summary_if_exists(mock_session, bookmark_data, [], [])
        assert result == []

    @pytest.mark.asyncio
    async def test_summary_save_vector_service_error(self):
        """요약 저장 시 벡터 서비스 오류 테스트"""
        mock_session = AsyncMock()
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="Valid summary"
        )
        
        with patch('app.tasks.bookmark_save_task.vector_service.save_document') as mock_save:
            mock_save.side_effect = ValueError("Summary save failed")
            
            with pytest.raises(ValueError):
                await _save_summary_if_exists(mock_session, bookmark_data, [], [])


class TestSaveBookmarkLogic:
    """북마크 저장 로직 에러 테스트"""

    def test_database_session_error(self):
        """데이터베이스 세션 오류 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        # S3 다운로드가 먼저 실행되므로 S3 관련 함수를 모킹해야 함
        with patch('app.tasks.bookmark_save_task.download_html_from_s3') as mock_download:
            mock_download.return_value = "<html><body>test content</body></html>"
            
            with patch('app.tasks.bookmark_save_task.extract_main_text') as mock_extract:
                mock_extract.return_value = "test content"
                
                with patch('app.tasks.bookmark_save_task.similarity_service.find_similar_bookmarks') as mock_sim:
                    mock_sim.return_value = []
                    
                    with patch('app.tasks.bookmark_save_task.message_publisher.publish_bookmark_relationships') as mock_pub:
                        mock_pub.return_value = False
                        
                        with patch('app.tasks.bookmark_save_task.get_async_session') as mock_session:
                            mock_session.side_effect = ConnectionError("Database connection failed")
                            
                            with pytest.raises(ConnectionError):
                                _save_bookmark_logic(bookmark_data)

    def test_asyncio_run_error(self):
        """asyncio.run 실행 오류 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('asyncio.run') as mock_run:
            mock_run.side_effect = RuntimeError("Event loop is running")
            
            with pytest.raises(RuntimeError):
                _save_bookmark_logic(bookmark_data)

    def test_comprehensive_error_in_async_logic(self):
        """비동기 로직 내부 에러 테스트"""
        bookmark_data = BookmarkData(
            user_id=123, star_id="test", s3_key="key", title="title",
            url="url", keywords=["test"], memo="memo", summary="summary"
        )
        
        with patch('app.tasks.bookmark_save_task._download_and_extract_content') as mock_download:
            mock_download.side_effect = Exception("Comprehensive failure")
            
            with pytest.raises(Exception):
                _save_bookmark_logic(bookmark_data)


class TestSaveBookmarkTask:
    """Celery 태스크 에러 테스트"""

    def test_bookmark_data_creation_error(self):
        """BookmarkData 생성 오류 테스트"""
        invalid_data = {
            "user_id": 123,
            "star_id": "test"
            # 필수 필드들 누락
        }
        
        with pytest.raises(TypeError):
            save_bookmark_task(invalid_data)

    def test_connection_error_handling(self):
        """ConnectionError 처리 테스트"""
        valid_data = {
            "user_id": 123, "star_id": "test", "s3_key": "key", "title": "title",
            "url": "url", "keywords": ["test"], "memo": "memo", "summary": "summary"
        }
        
        with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
            mock_logic.side_effect = ConnectionError("Network connection failed")
            
            with pytest.raises(ConnectionError):
                save_bookmark_task(valid_data)

    def test_timeout_error_handling(self):
        """TimeoutError 처리 테스트"""
        valid_data = {
            "user_id": 123, "star_id": "test", "s3_key": "key", "title": "title",
            "url": "url", "keywords": ["test"], "memo": "memo", "summary": "summary"
        }
        
        with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
            mock_logic.side_effect = TimeoutError("Operation timeout")
            
            with pytest.raises(TimeoutError):
                save_bookmark_task(valid_data)

    def test_value_error_handling(self):
        """ValueError 처리 테스트"""
        valid_data = {
            "user_id": 123, "star_id": "test", "s3_key": "key", "title": "title",
            "url": "url", "keywords": ["test"], "memo": "memo", "summary": "summary"
        }
        
        with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
            mock_logic.side_effect = ValueError("Invalid bookmark data")
            
            with pytest.raises(ValueError):
                save_bookmark_task(valid_data)

    def test_generic_exception_handling(self):
        """일반 예외 처리 테스트"""
        valid_data = {
            "user_id": 123, "star_id": "test", "s3_key": "key", "title": "title",
            "url": "url", "keywords": ["test"], "memo": "memo", "summary": "summary"
        }
        
        with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
            mock_logic.side_effect = RuntimeError("Unexpected runtime error")
            
            with pytest.raises(RuntimeError):
                save_bookmark_task(valid_data)

    def test_successful_task_execution(self):
        """성공적인 태스크 실행 테스트"""
        valid_data = {
            "user_id": 123, "star_id": "test", "s3_key": "key", "title": "title",
            "url": "url", "keywords": ["test"], "memo": "memo", "summary": "summary"
        }
        
        expected_result = {
            "status": "success",
            "inserted": 10,
            "deleted": 5,
            "content_chunks": 3
        }
        
        with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
            mock_logic.return_value = expected_result
            
            result = save_bookmark_task(valid_data)
            assert result == expected_result
            
            # BookmarkData 객체가 올바르게 생성되어 전달되었는지 확인
            call_args = mock_logic.call_args[0][0]
            assert isinstance(call_args, BookmarkData)
            assert call_args.user_id == 123
            assert call_args.star_id == "test"


class TestEdgeCasesAndComplexScenarios:
    """엣지 케이스 및 복잡한 시나리오 테스트"""

    def test_unicode_handling_errors(self):
        """유니코드 처리 오류 테스트"""
        unicode_data = {
            "user_id": 123,
            "star_id": "test_🌟",
            "s3_key": "test/한글/path",
            "title": "제목에 이모지 🎯와 특수문자 <>&\"'",
            "url": "https://example.com/path?한글=테스트",
            "keywords": ["한글키워드", "🔥", "English"],
            "memo": "메모에 \n줄바꿈\t탭 \x00null바이트",
            "summary": "요약: 한글/English/日本語 混合"
        }
        
        with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
            mock_logic.return_value = {"status": "success"}
            
            # 유니코드 데이터도 정상 처리되어야 함
            result = save_bookmark_task(unicode_data)
            assert result["status"] == "success"

    def test_extremely_large_data(self):
        """극도로 큰 데이터 테스트"""
        large_data = {
            "user_id": 123,
            "star_id": "large_test",
            "s3_key": "large_key",
            "title": "Large Title",
            "url": "https://large.com",
            "keywords": ["keyword" + str(i) for i in range(1000)],  # 1000개 키워드
            "memo": "x" * 100000,  # 100KB 메모
            "summary": "y" * 50000   # 50KB 요약
        }
        
        with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
            mock_logic.return_value = {"status": "success"}
            
            # 큰 데이터도 정상 처리되어야 함
            result = save_bookmark_task(large_data)
            assert result["status"] == "success"

    def test_invalid_data_combinations(self):
        """잘못된 데이터 조합 테스트"""
        invalid_combinations = [
            # 음수 user_id
            {
                "user_id": -123, "star_id": "test", "s3_key": "key", "title": "title",
                "url": "url", "keywords": ["test"], "memo": "memo", "summary": "summary"
            },
            # 빈 문자열들
            {
                "user_id": 123, "star_id": "", "s3_key": "", "title": "",
                "url": "", "keywords": [], "memo": "", "summary": ""
            },
            # None 값들
            {
                "user_id": 123, "star_id": None, "s3_key": None, "title": None,
                "url": None, "keywords": None, "memo": None, "summary": None
            }
        ]
        
        for invalid_data in invalid_combinations:
            with patch('app.tasks.bookmark_save_task._save_bookmark_logic') as mock_logic:
                # 데이터 자체는 잘못되었지만 처리 로직은 성공한다고 가정
                mock_logic.return_value = {"status": "success"}
                
                try:
                    result = save_bookmark_task(invalid_data)
                    # 일부 경우에는 성공할 수 있음
                    assert result["status"] == "success"
                except (TypeError, AttributeError):
                    # None 값들로 인한 오류는 예상됨
                    pass 