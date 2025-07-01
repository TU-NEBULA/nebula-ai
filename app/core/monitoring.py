"""
모니터링 및 메트릭 수집 설정 모듈

이 모듈은 Prometheus 메트릭 수집, 커스텀 메트릭 정의, 
성능 모니터링을 위한 설정을 관리합니다.
"""

import time
import asyncio
import psutil
from prometheus_client import Counter, Histogram, Gauge, start_http_server, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from fastapi import FastAPI, Request, Response
from typing import Callable
from loguru import logger


# 커스텀 Prometheus 메트릭 정의
class PrometheusMetrics:
    """Prometheus 메트릭 정의 클래스"""
    
    def __init__(self):
        # HTTP 요청 관련 메트릭
        self.http_requests_total = Counter(
            "http_requests_total",
            "총 HTTP 요청 수",
            ["method", "endpoint", "status"]
        )
        
        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP 요청 처리 시간",
            ["method", "endpoint"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
        )
        
        # 애플리케이션 특화 메트릭
        self.bookmark_operations_total = Counter(
            "bookmark_operations_total",
            "북마크 작업 수",
            ["operation", "status"]
        )
        
        self.recommendation_requests_total = Counter(
            "recommendation_requests_total",
            "추천 요청 수",
            ["type", "status"]
        )
        
        self.vector_operations_total = Counter(
            "vector_operations_total",
            "벡터 연산 수",
            ["operation", "status"]
        )
        
        self.clustering_operations_total = Counter(
            "clustering_operations_total",
            "클러스터링 작업 수",
            ["operation", "status"]
        )
        
        # 성능 메트릭
        self.database_query_duration = Histogram(
            "database_query_duration_seconds",
            "데이터베이스 쿼리 실행 시간",
            ["query_type", "table"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
        )
        
        self.external_api_duration = Histogram(
            "external_api_duration_seconds",
            "외부 API 호출 시간",
            ["service", "endpoint"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
        )
        
        self.celery_task_duration = Histogram(
            "celery_task_duration_seconds",
            "Celery 작업 실행 시간",
            ["task_name", "status"],
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0)
        )
        
        # 시스템 리소스 메트릭
        self.memory_usage_bytes = Gauge(
            "memory_usage_bytes",
            "메모리 사용량 (바이트)"
        )
        
        self.cpu_usage_percent = Gauge(
            "cpu_usage_percent",
            "CPU 사용률 (%)"
        )
        
        self.active_connections = Gauge(
            "active_connections",
            "활성 연결 수",
            ["type"]
        )
        
        # 비즈니스 메트릭
        self.user_sessions_active = Gauge(
            "user_sessions_active",
            "활성 사용자 세션 수"
        )
        
        self.recommendation_ctr = Gauge(
            "recommendation_ctr",
            "추천 클릭률"
        )
        
        self.bookmark_save_rate = Gauge(
            "bookmark_save_rate",
            "북마크 저장률"
        )

    def increment_bookmark_operation(self, operation: str, status: str = "success"):
        """북마크 작업 메트릭 증가"""
        self.bookmark_operations_total.labels(operation=operation, status=status).inc()
    
    def increment_recommendation_request(self, rec_type: str, status: str = "success"):
        """추천 요청 메트릭 증가"""
        self.recommendation_requests_total.labels(type=rec_type, status=status).inc()
    
    def record_database_query(self, query_type: str, table: str, duration: float):
        """데이터베이스 쿼리 시간 기록"""
        self.database_query_duration.labels(query_type=query_type, table=table).observe(duration)
    
    def record_external_api_call(self, service: str, endpoint: str, duration: float):
        """외부 API 호출 시간 기록"""
        self.external_api_duration.labels(service=service, endpoint=endpoint).observe(duration)
    
    def record_celery_task(self, task_name: str, status: str, duration: float):
        """Celery 작업 시간 기록"""
        self.celery_task_duration.labels(task_name=task_name, status=status).observe(duration)
    
    def update_system_metrics(self):
        """시스템 리소스 메트릭 업데이트"""
        try:
            # 메모리 사용량
            memory = psutil.virtual_memory()
            self.memory_usage_bytes.set(memory.used)
            
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage_percent.set(cpu_percent)
            
        except Exception as e:
            logger.error(f"시스템 메트릭 업데이트 실패: {e}")


# 전역 메트릭 인스턴스
prometheus_metrics = PrometheusMetrics()


def setup_prometheus_metrics(app: FastAPI) -> Instrumentator:
    """
    FastAPI 애플리케이션에 Prometheus 메트릭 설정
    
    Args:
        app: FastAPI 애플리케이션 인스턴스
        
    Returns:
        Instrumentator 인스턴스
    """
    
    # Instrumentator 초기화
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="nebula_ai_requests_inprogress",
        inprogress_labels=True
    )
    
    # 기본 메트릭 추가
    instrumentator.add(
        metrics.request_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            metric_namespace="nebula_ai",
            metric_subsystem="http"
        )
    ).add(
        metrics.response_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            metric_namespace="nebula_ai",
            metric_subsystem="http"
        )
    )
    
    # 커스텀 메트릭 추가
    @instrumentator.add()
    def custom_request_metrics(info: metrics.Info) -> None:
        """커스텀 요청 메트릭 수집"""
        prometheus_metrics.http_requests_total.labels(
            method=info.method,
            endpoint=info.modified_handler,
            status=info.response.status_code
        ).inc()
        
        prometheus_metrics.http_request_duration.labels(
            method=info.method,
            endpoint=info.modified_handler
        ).observe(info.modified_duration)
    
    # 애플리케이션에 설정 적용
    instrumentator.instrument(app)
    
    # 메트릭 엔드포인트 노출
    instrumentator.expose(app, endpoint="/metrics")
    
    return instrumentator


async def start_system_metrics_collector():
    """시스템 메트릭 수집기 시작"""
    logger.info("🔍 시스템 메트릭 수집기 시작")
    
    while True:
        try:
            prometheus_metrics.update_system_metrics()
            await asyncio.sleep(15)  # 15초마다 시스템 메트릭 업데이트
        except Exception as e:
            logger.error(f"시스템 메트릭 수집 오류: {e}")
            await asyncio.sleep(60)  # 오류 시 1분 대기


def get_prometheus_metrics() -> PrometheusMetrics:
    """전역 Prometheus 메트릭 인스턴스 반환"""
    return prometheus_metrics


# 데코레이터들
def monitor_database_query(query_type: str, table: str):
    """데이터베이스 쿼리 모니터링 데코레이터"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                prometheus_metrics.record_database_query(query_type, table, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                prometheus_metrics.record_database_query(f"{query_type}_error", table, duration)
                raise e
        return wrapper
    return decorator


def monitor_external_api(service: str, endpoint: str):
    """외부 API 호출 모니터링 데코레이터"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                prometheus_metrics.record_external_api_call(service, endpoint, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                prometheus_metrics.record_external_api_call(f"{service}_error", endpoint, duration)
                raise e
        return wrapper
    return decorator


def monitor_celery_task(task_name: str):
    """Celery 작업 모니터링 데코레이터"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                prometheus_metrics.record_celery_task(task_name, "success", duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                prometheus_metrics.record_celery_task(task_name, "error", duration)
                raise e
        return wrapper
    return decorator 