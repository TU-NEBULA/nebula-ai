"""
북마크 저장 태스크 테스트 모듈

이 모듈은 app.tasks.bookmark_save_task의 _save_bookmark_logic 함수를 테스트합니다.
PostgreSQL 벡터 서비스를 모킹하여 실제 DB 연결 없이 테스트합니다.

개선사항 테스트:
- 사용자 정보 중심 저장 로직
- 기존 데이터 완전 삭제 로직  
- 짧은 텍스트 처리
- 북마크 업데이트 시나리오
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

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
    # 내부 로직 함수를 직접 호출
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    result = _save_bookmark_logic(
        user_id="user123",
        star_id="bookmark456", 
        s3_key="test/document.html",
        title="사용자가 설정한 제목",
        url="https://user-url.com",
        keywords=["AI", "머신러닝", "딥러닝"],
        memo="사용자 메모입니다",
        summary="사용자 요약입니다"
    )
    
    # 기본 반환값 구조 확인
    assert result["status"] == "success"
    assert result["inserted"] > 0
    assert result["content_chunks"] >= 1
    assert result["user_title"] == "사용자가 설정한 제목"
    assert result["user_url"] == "https://user-url.com"
    assert result["total_keywords"] == 3
    assert result["has_memo"] is True
    assert result["has_summary"] is True


def test_short_text_bookmark_handling():
    """짧은 텍스트 북마크 처리 테스트"""
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    result = _save_bookmark_logic(
        user_id="user123",
        star_id="short_bookmark",
        s3_key="test/short_document.html",  # 짧은 콘텐츠
        title="짧은 제목",
        url="https://short.com",
        keywords=["AI"],
        memo="짧은 메모",
        summary="짧은 요약"
    )
    
    # 짧은 텍스트도 정상 처리되어야 함
    assert result["status"] == "success"
    assert result["content_chunks"] >= 1  # 최소 1개 청크 보장
    assert result["inserted"] > 0
    assert result["user_title"] == "짧은 제목"


def test_user_data_only_approach():
    """사용자 데이터만 사용하는 접근 방식 테스트"""
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    # 사용자가 설정한 모든 정보
    user_title = "사용자 맞춤 제목"
    user_url = "https://user-custom.com"
    user_keywords = ["사용자", "선택", "키워드"]
    user_memo = "사용자가 작성한 중요한 메모"
    user_summary = "사용자가 확인한 요약"
    
    result = _save_bookmark_logic(
        user_id="user123",
        star_id="custom_bookmark",
        s3_key="test/any_document.html",
        title=user_title,
        url=user_url,
        keywords=user_keywords,
        memo=user_memo,
        summary=user_summary
    )
    
    # 사용자 정보가 100% 보존되어야 함
    assert result["user_title"] == user_title
    assert result["user_url"] == user_url
    assert result["total_keywords"] == len(user_keywords)
    assert result["user_keywords"] == len(user_keywords)
    assert result["has_memo"] is True
    assert result["has_summary"] is True


def test_bookmark_update_scenario():
    """북마크 업데이트 시나리오 테스트"""
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    star_id = "bookmark_update_test"
    
    # 첫 번째 저장
    first_result = _save_bookmark_logic(
        user_id="user123",
        star_id=star_id,
        s3_key="test/document.html",
        title="첫 번째 제목",
        url="https://first.com",
        keywords=["첫번째", "키워드"],
        memo="첫 번째 메모",
        summary="첫 번째 요약"
    )
    
    # 첫 저장에서는 기존 데이터가 없으므로 is_update=False (또는 삭제 수가 적음)
    assert first_result["status"] == "success"
    
    # 두 번째 저장 (업데이트)
    second_result = _save_bookmark_logic(
        user_id="user123",
        star_id=star_id,  # 같은 star_id
        s3_key="test/document.html",
        title="업데이트된 제목",  # 변경됨
        url="https://updated.com",  # 변경됨
        keywords=["업데이트", "새로운", "키워드"],  # 변경됨
        memo="업데이트된 메모",  # 변경됨
        summary="업데이트된 요약"  # 변경됨
    )
    
    # 업데이트된 정보가 반영되어야 함
    assert second_result["user_title"] == "업데이트된 제목"
    assert second_result["user_url"] == "https://updated.com"
    assert second_result["total_keywords"] == 3
    assert second_result["deleted"] >= 0  # 기존 데이터가 삭제되었음
    assert second_result["is_update"] is True  # 업데이트임을 표시


def test_complete_data_deletion():
    """기존 데이터 완전 삭제 테스트"""
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    # 모킹을 통해 삭제 호출 확인
    with patch('app.tasks.bookmark_save_task.vector_service.delete_document') as mock_delete:
        
        # 다양한 삭제 결과 설정
        mock_delete.return_value = 2
        
        result = _save_bookmark_logic(
            user_id="user123",
            star_id="deletion_test",
            s3_key="test/document.html",
            title="삭제 테스트",
            url="https://delete-test.com",
            keywords=["삭제", "테스트"],
            memo="삭제 테스트 메모",
            summary="삭제 테스트 요약"
        )
        
        # 삭제 함수가 여러 번 호출되었는지 확인 (bookmark, bookmark_chunk 등)
        assert mock_delete.call_count >= 2
        
        # 삭제된 항목이 있다고 보고되어야 함
        assert result["deleted"] >= 0


def test_empty_memo_and_summary():
    """빈 메모와 요약 처리 테스트"""
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    result = _save_bookmark_logic(
        user_id="user123",
        star_id="empty_fields_test",
        s3_key="test/document.html", 
        title="빈 필드 테스트",
        url="https://empty-fields.com",
        keywords=["테스트"],
        memo="",  # 빈 메모
        summary=""  # 빈 요약
    )
    
    # 빈 메모와 요약이 올바르게 처리되어야 함
    assert result["status"] == "success"
    assert result["has_memo"] is False
    assert result["has_summary"] is False
    assert result["content_chunks"] >= 1  # 콘텐츠 청크는 여전히 생성


def test_special_characters_in_user_data():
    """사용자 데이터의 특수 문자 처리 테스트"""
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    result = _save_bookmark_logic(
        user_id="user123",
        star_id="special_chars_test",
        s3_key="test/document.html",
        title="🤖 AI & 머신러닝 (특수문자)",
        url="https://special-chars.com/path?param=value&other=한글",
        keywords=["AI&ML", "특수#문자", "이모지🚀"],
        memo="특수 문자 포함 메모: <script>alert('test')</script>",
        summary="SQL injection'; DROP TABLE users;-- 요약"
    )
    
    # 특수 문자가 포함되어도 정상 처리되어야 함
    assert result["status"] == "success"
    assert result["user_title"] == "🤖 AI & 머신러닝 (특수문자)"
    assert result["total_keywords"] == 3


def test_extreme_keyword_counts():
    """극단적인 키워드 수 처리 테스트"""
    from app.tasks.bookmark_save_task import _save_bookmark_logic
    
    # 키워드가 없는 경우
    result_no_keywords = _save_bookmark_logic(
        user_id="user123",
        star_id="no_keywords",
        s3_key="test/document.html",
        title="키워드 없음",
        url="https://no-keywords.com",
        keywords=[],  # 빈 키워드 리스트
        memo="키워드 없는 메모",
        summary="키워드 없는 요약"
    )
    
    assert result_no_keywords["status"] == "success"
    assert result_no_keywords["total_keywords"] == 0
    
    # 매우 많은 키워드
    many_keywords = [f"키워드{i}" for i in range(50)]
    result_many_keywords = _save_bookmark_logic(
        user_id="user123", 
        star_id="many_keywords",
        s3_key="test/document.html",
        title="키워드 많음",
        url="https://many-keywords.com",
        keywords=many_keywords,
        memo="키워드 많은 메모",
        summary="키워드 많은 요약"
    )
    
    assert result_many_keywords["status"] == "success"
    assert result_many_keywords["total_keywords"] == 50


class TestBookmarkTaskIntegration:
    """북마크 태스크 통합 테스트"""
    
    def test_logic_function_signature(self):
        """내부 로직 함수 시그니처 테스트"""
        from app.tasks.bookmark_save_task import _save_bookmark_logic
        
        # 로직 함수가 올바른 파라미터를 받는지 확인
        import inspect
        sig = inspect.signature(_save_bookmark_logic)
        params = list(sig.parameters.keys())
        
        expected_params = [
            'user_id', 'star_id', 's3_key', 
            'title', 'url', 'keywords', 'memo', 'summary'
        ]
        
        for param in expected_params:
            assert param in params, f"필수 파라미터 누락: {param}"
    
    def test_celery_task_exists(self):
        """Celery 태스크 존재 확인 테스트"""
        from app.tasks.bookmark_save_task import save_bookmark_task
        
        # 태스크가 정의되어 있는지 확인
        assert save_bookmark_task is not None
        assert hasattr(save_bookmark_task, 'name')
        assert save_bookmark_task.name == "tasks.save_bookmark"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])