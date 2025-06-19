"""
비동기 실행 유틸리티 모듈

Celery 워커 환경에서 안전하게 비동기 함수를 실행하기 위한 유틸리티 함수들을 제공합니다.
"""
import asyncio
import concurrent.futures
from typing import Any, Coroutine, TypeVar
from loguru import logger

T = TypeVar('T')

def run_async_safely(coro: Coroutine[Any, Any, T], timeout: int = 300) -> T:
    """
    Celery 워커 환경에서 안전하게 비동기 함수를 실행
    
    Args:
        coro: 실행할 코루틴
        timeout: 타임아웃 시간(초), 기본값 5분
        
    Returns:
        코루틴의 실행 결과
        
    Raises:
        TimeoutError: 타임아웃 발생 시
        Exception: 코루틴 실행 중 발생한 예외
    """
    try:
        # 현재 실행 중인 이벤트 루프가 있는지 확인
        loop = asyncio.get_running_loop()
        # 이미 이벤트 루프가 실행 중이면 새로운 스레드에서 실행
        logger.debug("기존 이벤트 루프 감지 - 새 스레드에서 실행")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result(timeout=timeout)
    except RuntimeError:
        # 이벤트 루프가 실행 중이지 않으면 일반적인 방법 사용
        logger.debug("새 이벤트 루프 생성하여 실행")
        return asyncio.run(coro)
    except Exception as e:
        logger.error("❌ 비동기 실행 중 오류: {}", e)
        raise

def run_async_safely_with_retries(
    coro: Coroutine[Any, Any, T], 
    max_retries: int = 3,
    timeout: int = 300,
    retry_delay: float = 1.0
) -> T:
    """
    재시도 기능이 있는 안전한 비동기 함수 실행
    
    Args:
        coro: 실행할 코루틴
        max_retries: 최대 재시도 횟수
        timeout: 타임아웃 시간(초)
        retry_delay: 재시도 간 지연시간(초)
        
    Returns:
        코루틴의 실행 결과
    """
    import time
    
    for attempt in range(max_retries + 1):
        try:
            return run_async_safely(coro, timeout=timeout)
        except Exception as e:
            if attempt == max_retries:
                logger.error("❌ 모든 재시도 실패 - 최종 오류: {}", e)
                raise
            
            logger.warning("⚠️ 재시도 {}/{} - 오류: {}", attempt + 1, max_retries, e)
            if retry_delay > 0:
                time.sleep(retry_delay) 