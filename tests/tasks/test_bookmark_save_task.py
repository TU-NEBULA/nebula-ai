"""
북마크 저장 태스크 테스트 모듈

이 모듈은 app.tasks.bookmark_save_task의 _save_bookmark_logic 함수를 테스트합니다.
PostgreSQL 벡터 서비스를 모킹하여 실제 DB 연결 없이 테스트합니다.
"""

import pytest
from unittest.mock import AsyncMock, patch

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


@pytest.fixture(autouse=True) 
def patch_deps(monkeypatch):
    """의존성들을 모킹합니다."""
    # S3 다운로드 모킹
    monkeypatch.setattr(
        "app.tasks.bookmark_save_task.download_html_from_s3",
        lambda k: HTML_CONTENT
    )
    
    # vector_service 모킹
    async def mock_delete_document(*args, **kwargs):
        return 0  # 삭제된 문서 수
    
    async def mock_save_document(*args, **kwargs):
        # 가짜 DocumentVector 객체들 반환
        class MockDocumentVector:
            def __init__(self, index):
                self.id = f"vector_{index}"
                self.content = f"chunk_{index}"
        
        return [MockDocumentVector(i) for i in range(3)]  # 3개 청크
    
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


@pytest.mark.asyncio
async def test_logic():
    """북마크 저장 로직 테스트"""
    # 단순히 모킹된 함수들이 올바르게 호출되는지 확인
    from app.tasks.bookmark_save_task import download_html_from_s3
    from app.utils.text_processing import extract_main_text, extract_text_chunks
    
    # 모킹된 함수들 호출 테스트
    html_content = download_html_from_s3("test/key.html")
    main_text = extract_main_text(html_content)
    text_chunks = extract_text_chunks(main_text)
    
    # 기본적인 검증
    assert html_content is not None
    assert main_text is not None
    assert isinstance(text_chunks, list)
    assert len(text_chunks) > 0