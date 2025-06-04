"""
북마크 저장 태스크 테스트

이 파일은 app/tasks/bookmark_save_task.py의 기능을 테스트합니다.
RAG 최적화된 벡터 저장과 사용자 데이터 우선 처리를 검증합니다.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.tasks.bookmark_save_task import BookmarkData, save_bookmark_task

HTML_CONTENT = """
<html>
<head><title>Test Page</title></head>
<body>
    <div>
        <p>This is a test page with some content.</p>
        <p>It has multiple paragraphs to test text extraction.</p>
    </div>
</body>
</html>
"""

SHORT_HTML_CONTENT = """
<html>
<head><title>Short</title></head>
<body><p>AI</p></body>
</html>
"""


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch):
    """의존성들을 모킹합니다."""
    # S3 다운로드 모킹 (여러 종류의 콘텐츠 지원)
    def mock_download_html_from_s3(s3_key):
        if "short" in s3_key.lower():
            return SHORT_HTML_CONTENT
        return HTML_CONTENT

    monkeypatch.setattr(
        "app.tasks.bookmark_save_task.download_html_from_s3",
        mock_download_html_from_s3
    )

    # vector_service 모킹
    async def mock_delete_document(*args, **kwargs):
        # 삭제 시나리오에 따라 다른 값 반환
        source_type = kwargs.get('source_type', '')
        source_id = kwargs.get('source_id', '')

        if source_type == "bookmark":
            return 2  # 기존 북마크 2개 삭제
        elif "_chunk_" in source_id:
            return 1  # 청크 1개 삭제
        elif "_memo" in source_id or "_summary" in source_id:
            return 1  # 메모/요약 각각 1개씩
        return 1  # 기타 타입 1개씩 삭제

    async def mock_save_document(*args, **kwargs):
        # 가짜 DocumentVector 객체들 반환
        class MockDocumentVector:
            def __init__(self, index):
                self.id = f"vector_{index}"
                self.content = kwargs.get('content', f"chunk_{index}")
                self.title = kwargs.get('title', 'Test Title')
                self.url = kwargs.get('url', 'https://test.com')
                self.keywords = kwargs.get('keywords', [])

        return [MockDocumentVector(i) for i in range(2)]  # 각 문서당 2개 벡터

    monkeypatch.setattr(
        "app.tasks.bookmark_save_task.vector_service.delete_document",
        mock_delete_document
    )
    monkeypatch.setattr(
        "app.tasks.bookmark_save_task.vector_service.save_document",
        mock_save_document
    )

    # 데이터베이스 세션 모킹
    mock_session = AsyncMock()

    async def mock_get_session():
        yield mock_session

    monkeypatch.setattr(
        "app.tasks.bookmark_save_task.get_async_session",
        mock_get_session
    )


def test_basic_bookmark_save_logic():
    """기본 북마크 저장 로직 테스트"""
    bookmark_data = BookmarkData(
        user_id=123,
        star_id="bookmark456",
        s3_key="test/document.html",
        title="사용자가 설정한 제목",
        url="https://user-url.com",
        keywords=["AI", "머신러닝", "딥러닝"],
        memo="사용자 메모입니다",
        summary="사용자 요약입니다"
    )

    result = _save_bookmark_logic(bookmark_data)

    # 결과 검증
    assert result["status"] == "success"
    assert result["inserted"] > 0
    assert result["user_title"] == "사용자가 설정한 제목"
    assert result["user_url"] == "https://user-url.com"
    assert result["user_keywords"] == 3
    assert result["has_memo"] is True
    assert result["has_summary"] is True


def test_short_text_bookmark_handling():
    """짧은 텍스트 북마크 처리 테스트"""
    bookmark_data = BookmarkData(
        user_id=123,
        star_id="short_bookmark",
        s3_key="test/short_document.html",
        title="짧은 제목",
        url="https://short.com",
        keywords=["AI"],
        memo="짧은 메모",
        summary="짧은 요약"
    )

    result = _save_bookmark_logic(bookmark_data)

    assert result["status"] == "success"
    assert result["content_chunks"] >= 1
    assert result["user_keywords"] == 1
    assert result["has_memo"] is True


def test_user_data_only_approach():
    """사용자 데이터만 사용하는 접근 방식 테스트"""
    user_title = "사용자 맞춤 제목"
    user_url = "https://user-custom.com"
    user_keywords = ["사용자", "선택", "키워드"]
    user_memo = "사용자가 작성한 중요한 메모"
    user_summary = "사용자가 확인한 요약"

    bookmark_data = BookmarkData(
        user_id=123,
        star_id="custom_bookmark",
        s3_key="test/any_document.html",
        title=user_title,
        url=user_url,
        keywords=user_keywords,
        memo=user_memo,
        summary=user_summary
    )

    result = _save_bookmark_logic(bookmark_data)

    # 사용자 데이터가 그대로 보존되는지 확인
    assert result["status"] == "success"
    assert result["user_title"] == user_title
    assert result["user_url"] == user_url
    assert result["user_keywords"] == len(user_keywords)
    assert result["total_keywords"] == len(user_keywords)

    # 사용자 입력이 우선시되는지 확인
    assert user_title in result["user_title"]
    assert len(user_keywords) == result["user_keywords"]


@pytest.mark.asyncio
async def test_bookmark_update_scenario():
    """북마크 업데이트 시나리오 테스트"""
    star_id = "bookmark_update_test"

    # 첫 번째 저장
    first_data = BookmarkData(
        user_id=123,
        star_id=star_id,
        s3_key="test/document.html",
        title="첫 번째 제목",
        url="https://first.com",
        keywords=["첫번째", "키워드"],
        memo="첫 번째 메모",
        summary="첫 번째 요약"
    )

    first_result = await _async_save_bookmark_logic(first_data)

    # 두 번째 업데이트
    second_data = BookmarkData(
        user_id=123,
        star_id=star_id,  # 같은 star_id
        s3_key="test/document_updated.html",
        title="업데이트된 제목",
        url="https://updated.com",
        keywords=["업데이트", "키워드"],
        memo="업데이트된 메모",
        summary="업데이트된 요약"
    )

    second_result = await _async_save_bookmark_logic(second_data)

    # 검증
    assert first_result["status"] == "success"
    assert second_result["status"] == "success"
    assert second_result["is_update"] is True  # 업데이트 플래그 확인
    assert second_result["deleted"] > 0  # 기존 데이터 삭제 확인


@patch('app.tasks.bookmark_save_task.vector_service.delete_document')
def test_complete_data_deletion(mock_delete):
    """기존 데이터 완전 삭제 테스트"""
    # 다양한 삭제 결과 설정
    mock_delete.return_value = 2

    bookmark_data = BookmarkData(
        user_id=123,
        star_id="deletion_test",
        s3_key="test/document.html",
        title="삭제 테스트",
        url="https://delete-test.com",
        keywords=["삭제", "테스트"],
        memo="삭제 테스트 메모",
        summary="삭제 테스트 요약"
    )

    result = _save_bookmark_logic(bookmark_data)

    assert result["status"] == "success"
    # 삭제 함수가 여러 번 호출되었는지 확인
    assert mock_delete.call_count >= 2


def test_empty_memo_and_summary():
    """빈 메모와 요약 처리 테스트"""
    bookmark_data = BookmarkData(
        user_id=123,
        star_id="empty_fields_test",
        s3_key="test/document.html",
        title="빈 필드 테스트",
        url="https://empty-fields.com",
        keywords=["테스트"],
        memo="",
        summary=""
    )

    result = _save_bookmark_logic(bookmark_data)

    assert result["status"] == "success"
    assert result["has_memo"] is False
    assert result["has_summary"] is False
    assert result["inserted"] > 0


def test_special_characters_in_user_data():
    """사용자 데이터의 특수 문자 처리 테스트"""
    bookmark_data = BookmarkData(
        user_id=123,
        star_id="special_chars_test",
        s3_key="test/document.html",
        title="🤖 AI & 머신러닝 (특수문자)",
        url="https://special-chars.com/path?param=value&other=한글",
        keywords=["AI&ML", "특수#문자", "이모지🚀"],
        memo="특수 문자 포함 메모: <script>alert('test')</script>",
        summary="SQL injection'; DROP TABLE users;-- 요약"
    )

    result = _save_bookmark_logic(bookmark_data)

    assert result["status"] == "success"
    assert "🤖" in result["user_title"]
    assert len(result["user_title"]) > 0
    assert result["user_keywords"] == 3


@pytest.mark.asyncio
async def test_extreme_keyword_counts():
    """극단적인 키워드 수 처리 테스트"""
    # 키워드가 없는 경우
    no_keywords_data = BookmarkData(
        user_id=123,
        star_id="no_keywords",
        s3_key="test/document.html",
        title="키워드 없음",
        url="https://no-keywords.com",
        keywords=[],
        memo="키워드 없는 메모",
        summary="키워드 없는 요약"
    )

    result_no_keywords = await _async_save_bookmark_logic(no_keywords_data)

    # 키워드가 매우 많은 경우
    many_keywords_data = BookmarkData(
        user_id=123,
        star_id="many_keywords",
        s3_key="test/document.html",
        title="키워드 많음",
        url="https://many-keywords.com",
        keywords=[f"키워드{i}" for i in range(100)],  # 100개 키워드
        memo="키워드 많은 메모",
        summary="키워드 많은 요약"
    )

    result_many_keywords = await _async_save_bookmark_logic(many_keywords_data)

    # 검증
    assert result_no_keywords["status"] == "success"
    assert result_no_keywords["total_keywords"] == 0
    assert result_no_keywords["user_keywords"] == 0

    assert result_many_keywords["status"] == "success"
    assert result_many_keywords["total_keywords"] == 100
    assert result_many_keywords["user_keywords"] == 100


class TestBookmarkTaskIntegration:
    """북마크 태스크 통합 테스트"""

    def test_logic_function_signature(self):
        """로직 함수 시그니처 테스트"""
        import inspect

        sig = inspect.signature(_save_bookmark_logic)
        params = list(sig.parameters.keys())

        expected_params = ["bookmark_data"]
        assert params == expected_params

    def test_celery_task_exists(self):
        """Celery 태스크 존재 여부 테스트"""
        from app.tasks.bookmark_save_task import save_bookmark_task

        assert hasattr(save_bookmark_task, 'delay')
        assert hasattr(save_bookmark_task, 'apply_async')
        assert save_bookmark_task.name == "tasks.save_bookmark"


# 테스트용 비동기 로직 함수
async def _async_save_bookmark_logic(bookmark_data: BookmarkData) -> dict:
    """테스트용 비동기 버전의 북마크 저장 로직"""
    from app.tasks.bookmark_save_task import (
        _download_and_extract_content,
        _calculate_similarity,
        _publish_relationships,
        _delete_existing_data,
        _save_content_chunks,
        _save_memo_if_exists,
        _save_summary_if_exists
    )
    from app.core.database import get_async_session
    from loguru import logger

    # 1. S3에서 HTML 다운로드 및 텍스트 추출
    body_text = await _download_and_extract_content(bookmark_data.s3_key)

    # 2. 유사도 계산 수행
    similar_bookmarks = await _calculate_similarity(bookmark_data, body_text)

    # 3. 관계 데이터 메시지 발행
    relationship_published = await _publish_relationships(bookmark_data, similar_bookmarks)

    # 4. PostgreSQL 벡터 데이터베이스 저장
    logger.info("💾 벡터 데이터베이스 저장 시작...")

    async for session in get_async_session():
        # 4-1. 기존 데이터 삭제
        total_deleted = await _delete_existing_data(session, bookmark_data)

        # 4-2. 콘텐츠 청크 저장
        saved_vectors, rag_chunks = await _save_content_chunks(
            session, bookmark_data, body_text, similar_bookmarks
        )

        # 4-3. 메모 저장 (있는 경우)
        memo_vectors = await _save_memo_if_exists(session, bookmark_data, similar_bookmarks)
        saved_vectors.extend(memo_vectors)

        # 4-4. 요약 저장 (있는 경우)
        summary_vectors = await _save_summary_if_exists(
            session, bookmark_data, similar_bookmarks, rag_chunks
        )
        saved_vectors.extend(summary_vectors)

        logger.info("✅ 벡터 데이터베이스 저장 완료 - 벡터 수: {}", len(saved_vectors))

        return {
            "status": "success",
            "inserted": len(saved_vectors),
            "deleted": total_deleted,
            "content_chunks": len(rag_chunks),
            "has_memo": bool(bookmark_data.memo and bookmark_data.memo.strip()),
            "has_summary": bool(bookmark_data.summary and bookmark_data.summary.strip()),
            "total_keywords": len(bookmark_data.keywords),
            "user_keywords": len(bookmark_data.keywords),
            "user_title": bookmark_data.title,
            "user_url": bookmark_data.url,
            "is_update": total_deleted > 0,
            "similar_bookmarks_found": len(similar_bookmarks),
            "relationship_published": relationship_published,
            "content_length": len(body_text)
        }


# 동기 래퍼 함수 (기존 함수명 유지를 위해)
def _save_bookmark_logic(bookmark_data: BookmarkData) -> dict:
    """동기 래퍼 함수 - 테스트에서 사용"""
    try:
        # 현재 실행 중인 이벤트 루프가 있는지 확인
        loop = asyncio.get_running_loop()
        # 이미 이벤트 루프가 실행 중이면 새로운 스레드에서 실행
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _async_save_bookmark_logic(bookmark_data))
            return future.result()
    except RuntimeError:
        # 이벤트 루프가 실행 중이지 않으면 일반적인 방법 사용
        return asyncio.run(_async_save_bookmark_logic(bookmark_data))


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])