import json
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from aio_pika import IncomingMessage

import app.consumers.bookmark_save_rmq as mod 

@pytest.mark.asyncio
async def test_on_bookmark_save_success():
    """정상적인 북마크 저장 메시지 처리 테스트"""
    
    # Mock Celery 태스크
    mock_task = MagicMock()
    mock_task.delay.return_value = None
    
    # 전역 인스턴스 교체
    original_task = mod.save_bookmark_task
    
    try:
        mod.save_bookmark_task = mock_task
        
        # 테스트 메시지 생성 (userId를 int로 변경)
        test_data = {
            "userId": 123,  # int 타입
            "starId": "star456",
            "s3Key": "test/path/file.html",
            "title": "테스트 북마크",
            "url": "https://example.com",
            "keywords": ["키워드1", "키워드2"],
            "memo": "테스트 메모",
            "summary": "테스트 요약"
        }
        
        # Mock 메시지 생성
        mock_message = MagicMock()
        mock_message.body = json.dumps(test_data).encode('utf-8')
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()
        
        # 함수 실행
        await mod.on_bookmark_save(mock_message)
        
        # 검증 - Celery 태스크가 올바른 파라미터로 호출되었는지 확인
        mock_task.delay.assert_called_once_with({
            "user_id": 123,  # int 타입
            "star_id": "star456",
            "s3_key": "test/path/file.html",
            "title": "테스트 북마크",
            "url": "https://example.com",
            "keywords": ["키워드1", "키워드2"], 
            "memo": "테스트 메모",
            "summary": "테스트 요약"
        })
        
    finally:
        # 원래 인스턴스 복원
        mod.save_bookmark_task = original_task

@pytest.mark.asyncio
async def test_on_bookmark_save_invalid():
    """잘못된 JSON 메시지 처리 테스트"""
    
    # Mock 메시지 (잘못된 JSON)
    mock_message = MagicMock()
    mock_message.body = b"invalid json"
    mock_message.process.return_value.__aenter__ = AsyncMock()
    mock_message.process.return_value.__aexit__ = AsyncMock()
    
    # Mock Celery 태스크 (호출되지 않아야 함)
    mock_task = MagicMock()
    original_task = mod.save_bookmark_task
    
    try:
        mod.save_bookmark_task = mock_task
        
        # 함수 실행 (예외 발생해도 정상 처리되어야 함)
        await mod.on_bookmark_save(mock_message)
        
        # 검증 - 태스크가 호출되지 않았는지 확인
        mock_task.delay.assert_not_called()
        
    finally:
        mod.save_bookmark_task = original_task

@pytest.mark.asyncio
async def test_on_bookmark_save_missing_required_fields():
    """필수 필드 누락 메시지 처리 테스트"""
    
    # 필수 필드가 누락된 메시지
    test_data = {
        "userId": 123,  # int 타입
        # "starId": "star456",  # 누락
        "s3Key": "test/path/file.html",
        "title": "테스트 북마크",
        "url": "https://example.com"
    }
    
    mock_message = MagicMock()
    mock_message.body = json.dumps(test_data).encode('utf-8')
    mock_message.process.return_value.__aenter__ = AsyncMock()
    mock_message.process.return_value.__aexit__ = AsyncMock()
    
    # Mock Celery 태스크 (호출되지 않아야 함)
    mock_task = MagicMock()
    original_task = mod.save_bookmark_task
    
    try:
        mod.save_bookmark_task = mock_task
        
        # 함수 실행 (예외 발생해도 정상 처리되어야 함)
        await mod.on_bookmark_save(mock_message)
        
        # 검증 - 태스크가 호출되지 않았는지 확인
        mock_task.delay.assert_not_called()
        
    finally:
        mod.save_bookmark_task = original_task

@pytest.mark.asyncio
async def test_on_bookmark_save_invalid_user_id():
    """유효하지 않은 userId 처리 테스트"""
    
    # Mock Celery 태스크 (호출되지 않아야 함)
    mock_task = MagicMock()
    original_task = mod.save_bookmark_task
    
    try:
        mod.save_bookmark_task = mock_task
        
        # 테스트 케이스들
        invalid_user_ids = [
            "not_a_number",  # 문자열
            -1,             # 음수
            0,              # 0
            None,           # None
            "123.45",       # 소수점
        ]
        
        for invalid_user_id in invalid_user_ids:
            test_data = {
                "userId": invalid_user_id,
                "starId": "star456",
                "s3Key": "test/path/file.html",
                "title": "테스트 북마크",
                "url": "https://example.com"
            }
            
            mock_message = MagicMock()
            mock_message.body = json.dumps(test_data).encode('utf-8')
            mock_message.process.return_value.__aenter__ = AsyncMock()
            mock_message.process.return_value.__aexit__ = AsyncMock()
            
            # 함수 실행 (예외 발생해도 정상 처리되어야 함)
            await mod.on_bookmark_save(mock_message)
        
        # 검증 - 태스크가 호출되지 않았는지 확인
        mock_task.delay.assert_not_called()
        
    finally:
        mod.save_bookmark_task = original_task

@pytest.mark.asyncio
async def test_start_bookmark_save_consumer(monkeypatch):
    """Consumer 시작 테스트"""
    calls = []
    
    class DummyQueue:
        def __init__(self, name):
            self.name = name
        async def consume(self, handler):
            calls.append(("consume", handler))
    
    class DummyChannel:
        async def set_qos(self, prefetch_count):
            calls.append(("set_qos", prefetch_count))
        async def declare_queue(self, queue_name, durable):
            calls.append(("declare_queue", queue_name, durable))
            return DummyQueue(queue_name)
    
    class DummyConnection:
        async def channel(self):
            return DummyChannel()
    
    async def fake_get_conn():
        return DummyConnection()
    
    monkeypatch.setattr(mod, "get_rabbit_connection", fake_get_conn)
    
    from app.core.config import settings
    settings.BOOKMARK_SAVE_QUEUE = "test.queue"
    
    await mod.start_bookmark_save_consumer()
    
    assert ("set_qos", 1) in calls  # 안전한 순차 처리
    assert ("declare_queue", "test.queue", True) in calls
    assert len([call for call in calls if call[0] == "consume"]) == 1
