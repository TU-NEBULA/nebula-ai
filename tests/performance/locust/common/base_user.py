"""
기본 사용자 클래스 모듈
HTTP와 RMQ 테스트에서 공통으로 사용하는 기능을 제공합니다.
"""

import time
from locust import events
from typing import Optional, Dict, Any


class BaseTestUser:
    """기본 테스트 사용자 클래스"""
    
    def __init__(self):
        self.user_id: Optional[int] = None
        self.session_id: Optional[str] = None
        self.start_time = time.time()
    
    def log_success(self, request_type: str, name: str, response_time: float, response_length: int = 0):
        """성공 이벤트 로깅"""
        events.request_success.fire(
            request_type=request_type,
            name=name,
            response_time=response_time,
            response_length=response_length
        )
    
    def log_failure(self, request_type: str, name: str, response_time: float, exception: Exception):
        """실패 이벤트 로깅"""
        events.request_failure.fire(
            request_type=request_type,
            name=name,
            response_time=response_time,
            exception=exception
        )
    
    def measure_time(self, start_time: float) -> float:
        """시간 측정 (밀리초 단위)"""
        return (time.time() - start_time) * 1000


class RequestTimer:
    """요청 시간 측정을 위한 컨텍스트 매니저"""
    
    def __init__(self, user: BaseTestUser, request_type: str, name: str):
        self.user = user
        self.request_type = request_type
        self.name = name
        self.start_time = None
        self.exception = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        response_time = self.user.measure_time(self.start_time)
        
        if exc_type is None:
            # 성공
            self.user.log_success(
                request_type=self.request_type,
                name=self.name,
                response_time=response_time
            )
        else:
            # 실패
            self.user.log_failure(
                request_type=self.request_type,
                name=self.name,
                response_time=response_time,
                exception=exc_val
            )
        
        # 예외를 다시 발생시키지 않음 (Locust가 처리하도록)
        return True


def create_timer(user: BaseTestUser, request_type: str, name: str) -> RequestTimer:
    """타이머 생성 헬퍼 함수"""
    return RequestTimer(user, request_type, name) 