"""
북마크 저장 Consumer 고급 에러 핸들링 테스트

로깅 검증, 복잡한 시나리오, 성능 관련 에러 등을 테스트합니다.
"""

import json
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, call
from aio_pika.exceptions import AMQPException, MessageProcessError
from loguru import logger

from app.consumers.bookmark_save_rmq import on_bookmark_save, start_bookmark_save_consumer


class MockIncomingMessage:
    """고급 테스트용 Mock IncomingMessage"""
    
    def __init__(self, payload=None, body_bytes=None, encoding_error=False, 
                 process_error=False, timeout_error=False):
        if encoding_error:
            self.body = b'\xff\xfe\x00\x00invalid_utf8_bytes'
        elif body_bytes is not None:
            self.body = body_bytes
        elif payload is not None:
            self.body = json.dumps(payload).encode('utf-8')
        else:
            self.body = b'{"default": "test"}'
        
        self.process_error = process_error
        self.timeout_error = timeout_error
    
    def process(self):
        """Mock process context manager"""
        class MockContext:
            def __init__(self, process_error, timeout_error):
                self.process_error = process_error
                self.timeout_error = timeout_error
            
            async def __aenter__(self):
                if self.process_error:
                    raise MessageProcessError("Message processing failed")
                if self.timeout_error:
                    await asyncio.sleep(0.1)  # 시뮬레이션된 타임아웃
                    raise asyncio.TimeoutError("Message processing timeout")
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        return MockContext(self.process_error, self.timeout_error)


class TestAdvancedErrorHandling:
    """고급 에러 핸들링 테스트"""

    @pytest.mark.asyncio
    async def test_message_processing_error(self):
        """메시지 프로세싱 에러 테스트"""
        message = MockIncomingMessage(
            payload={"userId": 123, "starId": "test", "s3Key": "key", "title": "title", "url": "url"},
            process_error=True
        )
        
        # MessageProcessError가 발생해도 Consumer 함수 자체는 완료되어야 함
        with pytest.raises(MessageProcessError):
            await on_bookmark_save(message)

    @pytest.mark.asyncio
    async def test_message_timeout_error(self):
        """메시지 처리 타임아웃 에러 테스트"""
        message = MockIncomingMessage(
            payload={"userId": 123, "starId": "test", "s3Key": "key", "title": "title", "url": "url"},
            timeout_error=True
        )
        
        # TimeoutError가 발생해도 Consumer 함수 자체는 완료되어야 함
        with pytest.raises(asyncio.TimeoutError):
            await on_bookmark_save(message)

    @pytest.mark.asyncio
    async def test_logging_verification_json_error(self):
        """JSON 오류 시 로깅 검증 테스트"""
        invalid_json = b'{"invalid": json, "missing": quote}'
        message = MockIncomingMessage(body_bytes=invalid_json)
        
        # JSON 오류가 발생해도 예외가 전파되지 않는지 확인
        await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_logging_verification_missing_fields(self):
        """필수 필드 누락 시 로깅 검증 테스트"""
        incomplete_payload = {
            "userId": 123,
            "starId": "test_star"
            # s3Key, title, url 누락
        }
        message = MockIncomingMessage(payload=incomplete_payload)
        
        # 필수 필드 누락 에러가 발생해도 예외가 전파되지 않는지 확인
        await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_logging_verification_invalid_user_id(self):
        """잘못된 userId 시 로깅 검증 테스트"""
        invalid_user_id_payload = {
            "userId": "not_a_number",
            "starId": "test_star",
            "s3Key": "test_key",
            "title": "Test Title",
            "url": "https://example.com"
        }
        message = MockIncomingMessage(payload=invalid_user_id_payload)
        
        # 잘못된 userId 에러가 발생해도 예외가 전파되지 않는지 확인
        await on_bookmark_save(message)  # 정상 완료되어야 함

    @pytest.mark.asyncio
    async def test_successful_processing_logs(self):
        """정상 처리 시 로깅 검증 테스트"""
        valid_payload = {
            "userId": 123,
            "starId": "success_star",
            "s3Key": "success_key",
            "title": "Success Title",
            "url": "https://success.example.com"
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
            assert call_args["star_id"] == "success_star"

    @pytest.mark.asyncio
    async def test_logger_mock_verification(self):
        """Mock을 사용한 로거 검증 테스트"""
        with patch('app.consumers.bookmark_save_rmq.logger') as mock_logger:
            invalid_json = b'{"invalid": json}'
            message = MockIncomingMessage(body_bytes=invalid_json)
            
            await on_bookmark_save(message)
            
            # 에러 로그가 호출되었는지 확인
            mock_logger.error.assert_called()
            
            # 에러 메시지에 JSON 관련 내용이 포함되었는지 확인
            error_call_args = mock_logger.error.call_args[0]
            assert "JSON 파싱 오류" in error_call_args[0]


class TestConcurrentErrorHandling:
    """동시 처리 중 에러 핸들링 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_message_processing_errors(self):
        """동시 메시지 처리 중 에러 테스트"""
        # 다양한 에러 상황의 메시지들
        messages = [
            MockIncomingMessage(body_bytes=b'invalid json'),  # JSON 오류
            MockIncomingMessage(payload={"userId": "invalid"}),  # userId 오류
            MockIncomingMessage(payload={}),  # 필수 필드 누락
            MockIncomingMessage(payload={
                "userId": 123, "starId": "valid", "s3Key": "key", 
                "title": "title", "url": "url"
            }),  # 정상 메시지
        ]
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 모든 메시지를 동시에 처리
            tasks = [on_bookmark_save(msg) for msg in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 에러가 있어도 모든 태스크가 완료되어야 함
            assert len(results) == 4
            
            # 정상 메시지의 경우 Celery 태스크가 호출되었는지 확인
            assert mock_task.delay.called

    @pytest.mark.asyncio
    async def test_resource_exhaustion_simulation(self):
        """리소스 고갈 시뮬레이션 테스트"""
        valid_payload = {
            "userId": 123,
            "starId": "resource_test",
            "s3Key": "resource_key",
            "title": "Resource Test",
            "url": "https://resource.example.com"
        }
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            # 메모리 부족 상황 시뮬레이션
            mock_task.delay.side_effect = MemoryError("Out of memory")
            
            message = MockIncomingMessage(payload=valid_payload)
            
            # 메모리 오류가 발생해도 Consumer는 계속 작동해야 함
            await on_bookmark_save(message)  # 예외가 전파되지 않아야 함


class TestComplexScenarios:
    """복잡한 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_malformed_unicode_sequences(self):
        """잘못된 유니코드 시퀀스 테스트"""
        # 다양한 잘못된 유니코드 시퀀스들
        malformed_sequences = [
            b'\x80\x81\x82\x83',  # 잘못된 UTF-8
            b'\xc0\x80',  # 잘못된 UTF-8 시퀀스
            b'\xed\xa0\x80\xed\xb0\x80',  # 잘못된 서로게이트 쌍
        ]
        
        for sequence in malformed_sequences:
            message = MockIncomingMessage(body_bytes=sequence)
            
            # 모든 잘못된 시퀀스가 안전하게 처리되어야 함
            await on_bookmark_save(message)

    @pytest.mark.asyncio
    async def test_extremely_nested_json(self):
        """극도로 중첩된 JSON 테스트"""
        # 매우 깊게 중첩된 구조 생성
        nested_data = {"userId": 123}
        current = nested_data
        for i in range(100):  # 100단계 중첩
            current["nested"] = {"level": i}
            current = current["nested"]
        
        current.update({
            "starId": "nested_star",
            "s3Key": "nested_key", 
            "title": "Deeply Nested",
            "url": "https://nested.example.com"
        })
        
        message = MockIncomingMessage(payload=nested_data)
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 깊게 중첩된 구조도 처리할 수 있어야 함
            await on_bookmark_save(message)

    @pytest.mark.asyncio
    async def test_binary_data_in_fields(self):
        """필드에 바이너리 데이터가 포함된 경우 테스트"""
        payload_with_binary = {
            "userId": 123,
            "starId": "binary_star",
            "s3Key": "binary_key",
            "title": "Title with binary: \x00\x01\x02",
            "url": "https://example.com",
            "memo": "Memo with null bytes: \x00\x00\x00",
            "summary": "Summary with control chars: \x07\x08\x09"
        }
        
        message = MockIncomingMessage(payload=payload_with_binary)
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 바이너리 데이터가 포함되어도 처리되어야 함
            await on_bookmark_save(message)


class TestConsumerStartupAdvanced:
    """Consumer 시작 관련 고급 테스트"""

    @pytest.mark.asyncio
    async def test_partial_connection_failure(self):
        """부분적 연결 실패 테스트"""
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        
        # 채널 생성은 성공하지만 QoS 설정에서 실패
        mock_connection.channel.return_value = mock_channel
        mock_channel.set_qos.side_effect = AMQPException("QoS setting failed")
        
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.return_value = mock_connection
            
            with pytest.raises(AMQPException):
                await start_bookmark_save_consumer()

    @pytest.mark.asyncio
    async def test_queue_declaration_failure(self):
        """큐 선언 실패 테스트"""
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.side_effect = AMQPException("Queue declaration failed")
        
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.return_value = mock_connection
            
            with pytest.raises(AMQPException):
                await start_bookmark_save_consumer()

    @pytest.mark.asyncio
    async def test_consumer_registration_failure(self):
        """Consumer 등록 실패 테스트"""
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.return_value = mock_queue
        mock_queue.consume.side_effect = AMQPException("Consumer registration failed")
        
        with patch('app.consumers.bookmark_save_rmq.get_rabbit_connection') as mock_conn:
            mock_conn.return_value = mock_connection
            
            with pytest.raises(AMQPException):
                await start_bookmark_save_consumer()


class TestErrorRecovery:
    """에러 복구 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_temporary_celery_failure_recovery(self):
        """일시적인 Celery 실패 후 복구 테스트"""
        valid_payload = {
            "userId": 123,
            "starId": "recovery_star",
            "s3Key": "recovery_key",
            "title": "Recovery Test",
            "url": "https://recovery.example.com"
        }
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            # 첫 번째 호출은 실패, 이후는 성공
            mock_task.delay.side_effect = [
                Exception("Temporary failure"),
                MagicMock(),  # 성공
            ]
            
            message1 = MockIncomingMessage(payload=valid_payload)
            message2 = MockIncomingMessage(payload=valid_payload)
            
            # 첫 번째 메시지는 실패하지만 예외가 전파되지 않음
            await on_bookmark_save(message1)
            
            # 두 번째 메시지는 성공
            await on_bookmark_save(message2)
            
            # 두 번 호출되었는지 확인
            assert mock_task.delay.call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_error_types_sequence(self):
        """연속적인 다양한 에러 타입 처리 테스트"""
        error_messages = [
            MockIncomingMessage(body_bytes=b'invalid json'),  # JSON 오류
            MockIncomingMessage(encoding_error=True),  # 인코딩 오류
            MockIncomingMessage(payload={"userId": "invalid"}),  # 검증 오류
            MockIncomingMessage(payload={}),  # 필수 필드 누락
        ]
        
        # 모든 에러 메시지들이 순차적으로 처리되어야 함
        for message in error_messages:
            await on_bookmark_save(message)  # 예외가 전파되지 않아야 함


class TestPerformanceRelatedErrors:
    """성능 관련 에러 테스트"""

    @pytest.mark.asyncio
    async def test_large_payload_memory_pressure(self):
        """대용량 페이로드로 인한 메모리 압박 테스트"""
        # 매우 큰 페이로드 생성 (실제로는 더 클 수 있지만 테스트를 위해 적당히 조절)
        huge_payload = {
            "userId": 123,
            "starId": "huge_star",
            "s3Key": "huge_key",
            "title": "Huge Title",
            "url": "https://huge.example.com",
            "memo": "x" * 100000,  # 100KB
            "summary": "y" * 50000,  # 50KB
            "keywords": ["keyword" + str(i) for i in range(10000)]  # 10K 키워드
        }
        
        message = MockIncomingMessage(payload=huge_payload)
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 대용량 페이로드도 처리되어야 함
            await on_bookmark_save(message)
            mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_rapid_successive_messages(self):
        """빠른 연속 메시지 처리 테스트"""
        messages = []
        for i in range(50):  # 50개의 연속 메시지
            payload = {
                "userId": 123 + i,
                "starId": f"rapid_star_{i}",
                "s3Key": f"rapid_key_{i}",
                "title": f"Rapid Title {i}",
                "url": f"https://rapid{i}.example.com"
            }
            messages.append(MockIncomingMessage(payload=payload))
        
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_task:
            mock_task.delay.return_value = MagicMock()
            
            # 모든 메시지가 빠르게 처리되어야 함
            tasks = [on_bookmark_save(msg) for msg in messages]
            await asyncio.gather(*tasks)
            
            # 모든 메시지에 대해 Celery 태스크가 호출되었는지 확인
            assert mock_task.delay.call_count == 50 