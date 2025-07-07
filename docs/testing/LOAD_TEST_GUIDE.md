# Nebula AI 부하 테스트 가이드

이 문서는 Locust를 사용한 Nebula AI 시스템의 부하 테스트 방법을 설명합니다.

## 목차

- [개요](#개요)
- [설치 및 설정](#설치-및-설정)
- [테스트 시나리오](#테스트-시나리오)
- [실행 방법](#실행-방법)
- [결과 분석](#결과-분석)
- [모니터링](#모니터링)
- [문제 해결](#문제-해결)

## 개요

Nebula AI는 다음 두 가지 주요 부하 테스트 시나리오를 지원합니다:

1. **HTTP API 부하 테스트**: FastAPI 엔드포인트 (채팅, 프로필, 추천 등)
2. **RabbitMQ 메시지 부하 테스트**: 북마크 생성, 데이터 추출 등의 비동기 작업

## 설치 및 설정

### 전제 조건

- Docker & Docker Compose
- 프로젝트 루트 디렉터리에서 실행

### 환경 구축

```bash
# 부하 테스트 환경 구축
make load-test-setup

# 또는 수동으로
docker compose -f docker/locust/docker-compose.locust.yml build
mkdir -p reports
```

## 테스트 시나리오

### 1. HTTP API 테스트 (`locust_chat_http.py`)

**대상 엔드포인트:**
- `POST /chat/stream` - 채팅 스트림 (가중치: 3)
- `GET /profile/{user_id}` - 사용자 프로필 조회 (가중치: 1)
- `GET /recommendations/{user_id}` - 추천 조회 (가중치: 1)

**테스트 데이터:**
- 1,000명의 가상 사용자 풀
- 5가지 채팅 메시지 템플릿
- 세션별 고유 ID 생성

### 2. RabbitMQ 메시지 테스트 (`locust_bookmark_rmq.py`)

**대상 큐:**
- `bookmark.create` - 북마크 생성 (가중치: 1)
- `extract.data` - 데이터 추출 (가중치: 2)

**테스트 데이터:**
- 10가지 URL 템플릿
- 랜덤 사용자 ID (1-1000)
- 태그 및 메타데이터 생성

## 실행 방법

### 1. 웹 UI를 통한 대화형 테스트

```bash
# HTTP API 테스트 UI
make load-test-ui-http
# 브라우저에서 http://localhost:8089 접속

# RabbitMQ 테스트 UI  
make load-test-ui-rmq
# 브라우저에서 http://localhost:8090 접속
```

### 2. Headless 자동 실행

```bash
# HTTP 부하 테스트 (기본: 200 사용자, 20/s 스폰, 5분)
make load-test-http

# 파라미터 커스터마이징
make load-test-http USERS=500 SPAWN_RATE=50 RUN_TIME=10m

# RabbitMQ 부하 테스트 (기본: 500 사용자, 50/s 스폰, 5분)
make load-test-rmq

# 모든 테스트 실행
make load-test-all
```

### 3. 직접 스크립트 실행

```bash
# HTTP 테스트
./scripts/run_locust_http.sh [users] [spawn_rate] [run_time]

# RabbitMQ 테스트  
./scripts/run_locust_rmq.sh [users] [spawn_rate] [run_time]
```

## 결과 분석

### CSV 리포트

Headless 실행 시 `reports/` 디렉터리에 다음 파일들이 생성됩니다:

- `*_stats.csv`: 요청별 통계 (평균, p50, p95, p99 응답시간)
- `*_failures.csv`: 실패한 요청 상세 정보
- `*_stats_history.csv`: 시간별 통계 변화

### 주요 지표

**성공 기준:**
- HTTP API: p95 응답시간 ≤ 2초, 실패율 < 1%
- RabbitMQ: 메시지 발행 성공률 ≥ 99.9%, p95 ≤ 100ms

**분석 포인트:**
```bash
# 실패율 확인
grep "fail_ratio" reports/*_stats.csv

# p95 응답시간 확인  
awk -F',' 'NR>1 {print $1, $8}' reports/*_stats.csv
```

## 모니터링

### Grafana 대시보드

모니터링과 함께 실행하려면:

```bash
# 모니터링 포함 실행
docker compose -f docker/locust/docker-compose.locust.yml --profile monitoring up

# 접속 URL
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
# - RabbitMQ Management: http://localhost:15672 (guest/guest)
```

### 실시간 모니터링 지표

**애플리케이션 지표:**
- CPU, 메모리 사용률
- 데이터베이스 연결 수
- Redis 연결 수

**RabbitMQ 지표:**
- 큐 길이 (`queue_messages_ready`)
- 소비자 수 (`queue_consumers`)
- 메시지 처리율 (`message_stats.deliver_get.rate`)

## 성능 튜닝 가이드

### 애플리케이션 튜닝

1. **Uvicorn Workers 조정**
   ```bash
   # docker-compose.yml에서
   command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

2. **데이터베이스 연결 풀**
   ```python
   # app/core/database.py
   SQLALCHEMY_DATABASE_URL = "postgresql://user:pass@host/db?pool_size=20&max_overflow=30"
   ```

### RabbitMQ 튜닝

1. **Prefetch Count 조정**
   ```python
   # consumers에서
   channel.basic_qos(prefetch_count=10)
   ```

2. **Consumer 수 증가**
   ```bash
   # Celery workers
   celery -A app.core.celery_worker worker --concurrency=8
   ```

## 문제 해결

### 자주 발생하는 문제

**1. 연결 오류**
```bash
# 컨테이너 네트워크 확인
docker network ls
docker compose -f docker/locust/docker-compose.locust.yml ps
```

**2. 메모리 부족**
```bash
# Docker 리소스 확인
docker stats
# 사용자 수 줄이기 또는 스폰 속도 감소
```

**3. RabbitMQ 연결 실패**
```bash
# RabbitMQ 상태 확인
docker compose -f docker/locust/docker-compose.locust.yml logs rabbitmq
# Management UI에서 큐 상태 확인: http://localhost:15672
```

### 로그 확인

```bash
# Locust 로그
docker compose -f docker/locust/docker-compose.locust.yml logs locust-http
docker compose -f docker/locust/docker-compose.locust.yml logs locust-rmq

# 애플리케이션 로그
docker compose -f docker/locust/docker-compose.locust.yml logs app
```

## CI/CD 통합

GitHub Actions 예시:

```yaml
- name: Run Load Tests
  run: |
    make load-test-setup
    make load-test-http USERS=100 RUN_TIME=2m
    make load-test-rmq USERS=200 RUN_TIME=2m
    
- name: Archive Results
  uses: actions/upload-artifact@v3
  with:
    name: load-test-results
    path: reports/
```

## 정리

```bash
# 테스트 환경 정리
make load-test-clean

# 또는 수동으로
docker compose -f docker/locust/docker-compose.locust.yml down -v
rm -rf reports/
```

---

**참고 자료:**
- [Locust 공식 문서](https://docs.locust.io/)
- [프로젝트 아키텍처 문서](../architecture.md)
- [모니터링 가이드](../monitoring_guide.md) 