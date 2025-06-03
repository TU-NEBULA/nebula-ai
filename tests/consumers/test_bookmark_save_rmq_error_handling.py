"""
북마크 저장 Consumer 에러 핸들링 테스트

다양한 오류 상황에서 Consumer가 올바르게 처리하는지 테스트합니다.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aio_pika.exceptions import AMQPException

from app.consumers.bookmark_save_rmq import on_bookmark_save, start_bookmark_save_consumer


class MockIncomingMessage:
    """테스트용 Mock IncomingMessage"""
    
    def __init__(self, payload=None, body_bytes=None, encoding_error=False):
        if encoding_error:
            # 잘못된 인코딩 시뮬레이션
            self.body = b'\xff\xfe\x00\x00invalid_utf8_bytes'
        elif body_bytes is not None:
            self.body = body_bytes
        elif payload is not None:
            self.body = json.dumps(payload).encode('utf-8')
        else:
            self.body = b'{"default": "test"}'
    
    def process(self):
        """Mock process context manager"""
        class MockContext:
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        return MockContext()


class TestBookmarkSaveConsumerErrorHandling:
    """북마크 저장 Consumer 에러 핸들링 테스트"""

    @pytest.mark.asyncio
    async def test_json_decode_error(self):
        """JSON 파싱 오류 테스트"""
        # 잘못된 JSON 형식
        invalid_json = b'{"invalid": json, "missing": quote}'
        message = MockIncomingMessage(body_bytes=invalid_json)
        
        # 에러가 발생해도 예외가 전파되지 않아야 함
        await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio 
    async def test_unicode_decode_error(self):
        """메시지 디코딩 오류 테스트"""
        message = MockIncomingMessage(encoding_error=True)
        
        # 인코딩 에러가 발생해도 예외가 전파되지 않아야 함
        await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """필수 필드 누락 오류 테스트"""
        test_cases = [
            # userId 누락
            {
                "starId": "test_star",
                "s3Key": "test_key",
                "title": "Test Title",
                "url": "https://example.com"
            },
            # starId 누락  
            {
                "userId": 123,
                "s3Key": "test_key",
                "title": "Test Title",
                "url": "https://example.com"
            },
            # s3Key 누락
            {
                "userId": 123,
                "starId": "test_star",
                "title": "Test Title", 
                "url": "https://example.com"
            },
            # title 누락
            {
                "userId": 123,
                "starId": "test_star",
                "s3Key": "test_key",
                "url": "https://example.com"
            },
            # url 누락
            {
                "userId": 123,
                "starId": "test_star", 
                "s3Key": "test_key",
                "title": "Test Title"
            }
        ]
        
        for case in test_cases:
            message = MockIncomingMessage(payload=case)
            
            # 필수 필드 누락 에러가 발생해도 예외가 전파되지 않아야 함
            await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_invalid_user_id_type(self):
        """잘못된 userId 타입 테스트"""
        test_cases = [
            # 문자열 (변환 불가능)
            {
                "userId": "invalid_number",
                "starId": "test_star",
                "s3Key": "test_key", 
                "title": "Test Title",
                "url": "https://example.com"
            },
            # 음수
            {
                "userId": -123,
                "starId": "test_star",
                "s3Key": "test_key",
                "title": "Test Title", 
                "url": "https://example.com"
            },
            # 0
            {
                "userId": 0,
                "starId": "test_star",
                "s3Key": "test_key",
                "title": "Test Title",
                "url": "https://example.com"
            },
            # null
            {
                "userId": None,
                "starId": "test_star",
                "s3Key": "test_key",
                "title": "Test Title",
                "url": "https://example.com"
            },
            # 소수점
            {
                "userId": 123.45,
                "starId": "test_star", 
                "s3Key": "test_key",
                "title": "Test Title",
                "url": "https://example.com"
            }
        ]
        
        for case in test_cases:
            message = MockIncomingMessage(payload=case)
            
            # userId 검증 에러가 발생해도 예외가 전파되지 않아야 함
            await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_celery_task_failure(self):
        """Celery 태스크 실행 실패 테스트"""
        valid_payload = {
            "userId": 123,
            "starId": "test_star",
            "s3Key": "test_key", 
            "title": "Test Title",
            "url": "https://example.com",
            "keywords": ["test", "keyword"],
            "memo": "Test memo",
            "summary": "Test summary"
        }
        
        message = MockIncomingMessage(payload=valid_payload)
        
        # Celery 태스크 실행 시 예외 발생 시뮬레이션
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.side_effect = Exception("Celery connection failed")
            
            # Celery 에러가 발생해도 Consumer는 정상 완료되어야 함
            await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_empty_message_body(self):
        """빈 메시지 바디 테스트"""
        message = MockIncomingMessage(body_bytes=b'')
        
        # 빈 메시지 에러가 발생해도 예외가 전파되지 않아야 함
        await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio 
    async def test_none_message_body(self):
        """None 메시지 바디 테스트"""
        # None을 처리하는 특별한 Mock
        class NoneBodyMessage:
            def __init__(self):
                self.body = None
            
            def process(self):
                class MockContext:
                    async def __aenter__(self):
                        return self
                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        pass
                return MockContext()
        
        message = NoneBodyMessage()
        
        # None 바디 에러가 발생해도 예외가 전파되지 않아야 함
        await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_valid_message_processing(self):
        """정상 메시지 처리 테스트 (에러 핸들링의 반대 케이스)"""
        valid_payload = {
            "userId": 123,
            "starId": "valid_star",
            "s3Key": "valid_key",
            "title": "Valid Title", 
            "url": "https://valid.example.com",
            "keywords": ["valid", "test"],
            "memo": "Valid memo",
            "summary": "Valid summary"
        }
        
        message = MockIncomingMessage(payload=valid_payload)
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 정상 처리되어야 함
            await on_bookmark_save(message)
            
            # Celery 태스크가 호출되었는지 확인
            mock_task.delay.assert_called_once()
            call_args = mock_task.delay.call_args[0][0]
            assert call_args["user_id"] == 123
            assert call_args["star_id"] == "valid_star"


class TestBookmarkSaveConsumerStartup:
    """북마크 저장 Consumer 시작 관련 에러 핸들링 테스트"""

    @pytest.mark.asyncio
    async def test_rabbitmq_connection_failure(self):
        """RabbitMQ 연결 실패 테스트"""
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.side_effect = AMQPException("Connection failed")
            
            # AMQPException이 재발생되어야 함
            with pytest.raises(AMQPException):
                await start_bookmark_save_consumer()

    @pytest.mark.asyncio
    async def test_network_connection_error(self):
        """네트워크 연결 오류 테스트"""
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.side_effect = ConnectionError("Network unreachable")
            
            # ConnectionError가 재발생되어야 함
            with pytest.raises(ConnectionError):
                await start_bookmark_save_consumer()

    @pytest.mark.asyncio
    async def test_os_error(self):
        """OS 에러 테스트"""
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.side_effect = OSError("No route to host")
            
            # OSError가 재발생되어야 함  
            with pytest.raises(OSError):
                await start_bookmark_save_consumer()

    @pytest.mark.asyncio 
    async def test_unexpected_startup_error(self):
        """예상하지 못한 시작 오류 테스트"""
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.side_effect = RuntimeError("Unexpected runtime error")
            
            # RuntimeError가 재발생되어야 함
            with pytest.raises(RuntimeError):
                await start_bookmark_save_consumer()

    @pytest.mark.asyncio
    async def test_consumer_startup_success_in_test_env(self):
        """테스트 환경에서 Consumer 시작 성공 테스트"""
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.return_value = mock_queue
        
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.return_value = mock_connection
            
            with patch('os.getenv') as mock_getenv:
                mock_getenv.return_value = "test_bookmark_save"  # 테스트 환경 시뮬레이션
                
                # 테스트 환경에서는 정상 완료되어야 함
                await start_bookmark_save_consumer()
                
                # 연결 및 큐 설정이 호출되었는지 확인
                mock_conn.assert_called_once()
                mock_connection.channel.assert_called_once()
                mock_channel.set_qos.assert_called_once_with(prefetch_count=1)
                mock_channel.declare_queue.assert_called_once()
                mock_queue.consume.assert_called_once()


class TestEdgeCases:
    """엣지 케이스 테스트"""
    
    @pytest.mark.asyncio
    async def test_very_large_message(self):
        """매우 큰 메시지 처리 테스트"""
        # 매우 큰 데이터 생성
        large_payload = {
            "userId": 123,
            "starId": "large_star",
            "s3Key": "large_key",
            "title": "Large Title",
            "url": "https://example.com",
            "memo": "x" * 10000,  # 10KB 텍스트
            "summary": "y" * 5000,  # 5KB 텍스트
            "keywords": ["keyword"] * 1000  # 1000개 키워드
        }
        
        message = MockIncomingMessage(payload=large_payload)
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 큰 메시지도 정상 처리되어야 함
            await on_bookmark_save(message)
            mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_special_characters_in_data(self):
        """특수 문자가 포함된 데이터 처리 테스트"""
        special_payload = {
            "userId": 123,
            "starId": "special_star_🌟",
            "s3Key": "special/key/with/한글/and/emojis/🔥", 
            "title": "제목에 특수문자가 있는 경우: <>&\"'",
            "url": "https://example.com/path?query=value&한글=테스트",
            "memo": "메모에도 이모지 🎯와 \n줄바꿈\t탭문자가 있을 수 있습니다",
            "summary": "요약: 한글/English/日本語/中文 混合",
            "keywords": ["한글키워드", "English", "🔥", "<script>"]
        }
        
        message = MockIncomingMessage(payload=special_payload)
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 특수 문자가 포함된 메시지도 정상 처리되어야 함
            await on_bookmark_save(message)
            mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_nested_json_structure(self):
        """중첩된 JSON 구조 처리 테스트"""
        nested_payload = {
            "userId": 123,
            "starId": "nested_star",
            "s3Key": "nested_key",
            "title": "Nested Title",
            "url": "https://example.com",
            "metadata": {  # 예상하지 못한 중첩 구조
                "nested": {
                    "deeply": {
                        "nested": "value"
                    }
                },
                "array": [1, 2, 3, {"inner": "object"}]
            }
        }
        
        message = MockIncomingMessage(payload=nested_payload)
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 중첩 구조가 있어도 정상 처리되어야 함
            await on_bookmark_save(message)
            mock_task.delay.assert_called_once() 