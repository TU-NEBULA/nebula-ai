"""
모니터링 및 메트릭 수집 설정 모듈

이 모듈은 Prometheus 메트릭 수집, 커스텀 메트릭 정의, 
성능 모니터링을 위한 설정을 관리합니다.
"""

import asyncio
import time

import psutil

try:
    from prometheus_client import (Counter, Gauge, Histogram, generate_latest,
                                   start_http_server)
    from prometheus_fastapi_instrumentator import Instrumentator, metrics
    PROMETHEUS_AVAILABLE = True
except ImportError:
    # Prometheus가 설치되지 않은 경우 더미 클래스들을 정의
    PROMETHEUS_AVAILABLE = False

    class Counter:
        """
        Counter 클래스는 Prometheus 메트릭 카운터를 나타냅니다.
        이 클래스는 특정 이벤트가 발생한 횟수를 추적하는 데 사용됩니다.
        예를 들어, HTTP 요청 수, 오류 발생 횟수 등을 추적할 때 사용됩니다.
        """
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass

    class Histogram:
        """
        Histogram 클래스는 Prometheus 메트릭 히스토그램을 나타냅니다.
        이 클래스는 특정 이벤트의 분포를 추적하는 데 사용됩니다.
        예를 들어, HTTP 요청 처리 시간, 데이터베이스 쿼리 시간 등을 추적할 때 사용됩니다.
        """
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
        def observe(self, *args, **kwargs):
            pass

    class Gauge:
        """
        Gauge 클래스는 Prometheus 메트릭 게이지를 나타냅니다.
        이 클래스는 특정 값을 추적하는 데 사용됩니다.
        예를 들어, 메모리 사용량, CPU 사용률 등을 추적할 때 사용됩니다.
        """
        def __init__(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass

    class Instrumentator:
        """
        Instrumentator 클래스는 Prometheus 메트릭 수집을 위한 도구를 제공합니다.
        이 클래스는 FastAPI 애플리케이션에서 메트릭을 수집하고 노출하는 데 사용됩니다.
        """
        def __init__(self, *args, **kwargs):
            pass
        def add(self, *args, **kwargs):
            return self
        def instrument(self, *args, **kwargs):
            pass
        def expose(self, *args, **kwargs):
            pass

    class metrics:
        """
        metrics 클래스는 Prometheus 메트릭 수집을 위한 도구를 제공합니다.
        이 클래스는 FastAPI 애플리케이션에서 메트릭을 수집하고 노출하는 데 사용됩니다.
        """
        @staticmethod
        def request_size(*args, **kwargs):
            pass
        @staticmethod
        def response_size(*args, **kwargs):
            pass

    def generate_latest():
        return "# Prometheus not available\n"

from typing import Callable

from fastapi import FastAPI, Request, Response
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
            buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0, 300.0)
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

        self.network_connections_active = Gauge(
            "network_connections_active",
            "활성 네트워크 연결 수",
            ["status"]
        )

        self.system_processes_active = Gauge(
            "system_processes_active", 
            "시스템 활성 프로세스 수"
        )

        self.system_processes_by_status = Gauge(
            "system_processes_by_status",
            "프로세스 상태별 분류",
            ["status"]
        )

        self.system_cpu_usage_per_process = Gauge(
            "system_cpu_usage_per_process", 
            "평균 프로세스당 CPU 사용률"
        )

        self.system_memory_usage_per_process = Gauge(
            "system_memory_usage_per_process",
            "평균 프로세스당 메모리 사용량"
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

        # FastAPI/Celery 작업 모니터링
        self.celery_tasks_pending = Gauge(
            "celery_tasks_pending",
            "대기 중인 Celery 작업 수",
            ["queue"]
        )

        self.celery_tasks_active = Gauge(
            "celery_tasks_active", 
            "실행 중인 Celery 작업 수",
            ["queue"]
        )

        self.celery_tasks_failed = Counter(
            "celery_tasks_failed_total",
            "실패한 Celery 작업 수",
            ["queue", "task_name"]
        )

        self.database_connections_pool = Gauge(
            "database_connections_pool",
            "데이터베이스 연결 풀 상태",
            ["status"]  # active, idle, overflow
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
        """Celery 태스크 실행 시간과 상태 기록"""
        if PROMETHEUS_AVAILABLE:
            # 태스크 실행 시간 기록
            self.http_request_duration.labels(method="CELERY", endpoint=task_name).observe(duration)

            # 실패한 경우 실패 카운터도 증가
            if status in ["error", "network_error", "data_error"]:
                # 큐 이름을 태스크 이름에서 추출 (예: save_bookmark -> bookmark_save)
                queue_name = self._extract_queue_from_task_name(task_name)
                self.celery_tasks_failed.labels(queue=queue_name, task_name=task_name).inc()

    def _extract_queue_from_task_name(self, task_name: str) -> str:
        """태스크 이름에서 큐 이름을 추출"""
        # 태스크 이름에서 큐 이름 매핑
        task_to_queue = {
            "save_bookmark": "bookmark_save",
            "update_user_profile": "user_profile", 
            "calculate_user_similarities": "user_analysis",
            "generate_recommendations": "recommendations",
            "analyze_trends": "analytics",
            "run_daily_quality_check": "monitoring"
        }
        return task_to_queue.get(task_name, "default")

    def increment_vector_operations(self, operation: str, status: str = "success"):
        """벡터 연산 메트릭 증가"""
        self.vector_operations_total.labels(operation=operation, status=status).inc()

    def increment_clustering_operations(self, operation: str, status: str = "success"):
        """클러스터링 작업 메트릭 증가"""
        self.clustering_operations_total.labels(operation=operation, status=status).inc()

    def update_system_metrics(self):
        """시스템 리소스 메트릭 업데이트"""
        try:
            logger.debug("시스템 메트릭 수집 시작")

            # 메모리 사용량
            memory = psutil.virtual_memory()
            self.memory_usage_bytes.set(memory.used)
            logger.debug(f"메모리 사용량: {memory.used / 1024 / 1024:.1f} MB")

            # CPU 사용률 (비블로킹 방식)
            cpu_percent = psutil.cpu_percent(interval=None)  # 즉시 반환, 이전 측정값 사용
            self.cpu_usage_percent.set(cpu_percent)
            logger.debug(f"CPU 사용률: {cpu_percent}%")

            # 활성 네트워크 연결 수
            try:
                network_connections = psutil.net_connections()

                # 연결 상태별로 분류
                connection_states = {}
                for conn in network_connections:
                    status = conn.status if conn.status else 'unknown'
                    connection_states[status] = connection_states.get(status, 0) + 1

                # 각 상태별로 메트릭 설정
                for status, count in connection_states.items():
                    self.network_connections_active.labels(status=status.lower()).set(count)

                logger.debug(f"네트워크 연결 상태: {connection_states}")

            except (psutil.AccessDenied, PermissionError) as e:
                logger.warning(f"네트워크 연결 정보 접근 권한 부족: {e}")

            # 활성 프로세스 수
            try:
                active_processes = len(psutil.pids())
                self.system_processes_active.set(active_processes)
                logger.debug(f"활성 프로세스 수: {active_processes}")
            except Exception as e:
                logger.warning(f"프로세스 수 수집 실패: {e}")

            # 프로세스 상태별 분류 및 리소스 사용량 수집
            process_states = {}
            cpu_usage_list = []
            memory_usage_list = []

            try:
                for proc in psutil.process_iter(['pid', 'status', 'cpu_percent', 'memory_info']):
                    try:
                        # 프로세스 상태 수집
                        status = proc.info['status']
                        process_states[status] = process_states.get(status, 0) + 1

                        # CPU 사용률 수집 (interval=None으로 즉시 반환)
                        cpu_percent = proc.info['cpu_percent'] or 0
                        cpu_usage_list.append(cpu_percent)

                        # 메모리 사용량 수집
                        memory_info = proc.info['memory_info']
                        if memory_info:
                            memory_usage_list.append(memory_info.rss)

                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        # 프로세스가 종료되었거나 접근 권한이 없는 경우 무시
                        continue

                # 각 상태별로 메트릭 설정
                for status, count in process_states.items():
                    self.system_processes_by_status.labels(status=status).set(count)

                # 평균 CPU 사용률 계산
                if cpu_usage_list:
                    avg_cpu = sum(cpu_usage_list) / len(cpu_usage_list)
                    self.system_cpu_usage_per_process.set(avg_cpu)

                # 평균 메모리 사용량 계산
                if memory_usage_list:
                    avg_memory = sum(memory_usage_list) / len(memory_usage_list)
                    self.system_memory_usage_per_process.set(avg_memory)

                logger.debug(f"프로세스 상태: {process_states}")

            except Exception as proc_error:
                logger.warning(f"프로세스 상태 수집 중 일부 오류: {proc_error}")
                # 기본 프로세스 수는 이미 설정되었으므로 계속 진행

            # Celery 큐 상태 수집
            self._update_celery_metrics()

            # 데이터베이스 연결 풀 상태 수집
            self._update_database_pool_metrics()

            logger.debug("시스템 메트릭 수집 완료")

        except ImportError as e:
            logger.error(f"psutil 라이브러리를 찾을 수 없음: {e}")
        except Exception as e:
            logger.error(f"시스템 메트릭 업데이트 실패: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")

    def _update_celery_metrics(self):
        """Celery 큐 상태 메트릭 수집"""
        try:
            from app.core.celery_worker import celery

            # Celery Inspector를 사용해서 큐 상태 조회
            inspect = celery.control.inspect()

            # 활성 작업 수집
            active_tasks = inspect.active()
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    # 큐별로 활성 작업 수 계산
                    queue_tasks = {}
                    for task in tasks:
                        queue = task.get('delivery_info', {}).get('routing_key', 'default')
                        queue_tasks[queue] = queue_tasks.get(queue, 0) + 1

                    # 메트릭 업데이트
                    for queue, count in queue_tasks.items():
                        self.celery_tasks_active.labels(queue=queue).set(count)

            # 예약된(대기 중인) 작업 수집
            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                for worker, tasks in scheduled_tasks.items():
                    queue_tasks = {}
                    for task in tasks:
                        queue = task.get('delivery_info', {}).get('routing_key', 'default')
                        queue_tasks[queue] = queue_tasks.get(queue, 0) + 1

                    for queue, count in queue_tasks.items():
                        self.celery_tasks_pending.labels(queue=queue).set(count)

        except Exception as e:
            logger.debug(f"Celery 메트릭 수집 실패 (정상적일 수 있음): {e}")

    def _update_database_pool_metrics(self):
        """데이터베이스 연결 풀 상태 메트릭 수집"""
        try:
            from app.core.database import engine

            pool = engine.pool

            # 연결 풀 상태 정보 수집
            active_connections = pool.checkedout()  # 사용 중인 연결
            idle_connections = pool.checkedin()     # 유휴 연결

            # 오버플로우 연결 (풀 크기 초과)
            overflow_connections = 0
            if hasattr(pool, 'overflow'):
                overflow_connections = pool.overflow()

            # 메트릭 업데이트
            self.database_connections_pool.labels(status="active").set(active_connections)
            self.database_connections_pool.labels(status="idle").set(idle_connections)
            self.database_connections_pool.labels(status="overflow").set(overflow_connections)

        except Exception as e:
            logger.debug(f"데이터베이스 풀 메트릭 수집 실패: {e}")

    def increment_celery_task_failure(self, queue_name: str, task_name: str):
        """Celery 작업 실패 카운터 증가 (태스크에서 수동 호출)"""
        if PROMETHEUS_AVAILABLE:
            self.celery_tasks_failed.labels(queue=queue_name, task_name=task_name).inc()


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

    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not available - metrics will be disabled")
        return Instrumentator()

    # Instrumentator 초기화
    instrumentator = Instrumentator(
        should_group_status_codes=False,                    # HTTP 상태 코드를 그룹화하지 않음 (200, 404 등을 개별 추적)
        should_ignore_untemplated=True,                     # 템플릿화되지 않은 경로는 무시
        should_respect_env_var=True,                        # 환경변수로 메트릭 활성화/비활성화 제어
        should_instrument_requests_inprogress=True,         # 진행 중인 요청 수 추적
        excluded_handlers=["/metrics", "/health"],          # 메트릭/헬스체크 엔드포인트는 추적 제외
        env_var_name="ENABLE_METRICS",                      # 메트릭 활성화 환경변수명
        inprogress_name="nebula_ai_requests_inprogress",    # 진행 중 요청 메트릭명
        inprogress_labels=True                              # 진행 중 요청에 라벨 추가
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
        # HTTP 요청 총 개수 카운터 증가
        prometheus_metrics.http_requests_total.labels(
            method=info.method,                 # GET, POST 등
            endpoint=info.modified_handler,     # /api/v1/profiles 등
            status=info.response.status_code    # 200, 404 등
        ).inc()

        # HTTP 요청 처리 시간 기록
        prometheus_metrics.http_request_duration.labels(
            method=info.method,
            endpoint=info.modified_handler
        ).observe(info.modified_duration)       # 실제 처리 시간 기록

    # 애플리케이션에 설정 적용
    instrumentator.instrument(app)

    # 메트릭 엔드포인트는 main.py에서 수동으로 설정됨
    # instrumentator.expose(app, endpoint="/metrics")

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
