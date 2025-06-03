# 🧪 북마크 저장 시스템 테스트 가이드

이 문서는 북마크 저장 시스템의 모든 테스트 방법과 절차를 설명합니다.

## 📂 테스트 구조

```
nebula-ai/
├── tests/
│   ├── manual/                  # 수동 테스트 스크립트
│   │   ├── consumer_test.py     # Consumer 단독 테스트
│   │   ├── task_test.py         # Task 단독 테스트
│   │   └── README.md            # 수동 테스트 가이드
│   ├── performance/             # 성능 테스트
│   │   └── bookmark_performance_test.py
│   ├── integration/             # 통합 테스트
│   └── unit/                    # 단위 테스트 (기존)
├── scripts/test/                # 테스트 설정 스크립트
│   └── setup_dev_environment.py
├── docker/test/                 # 테스트용 Docker 설정
│   └── docker-compose.test.yml
└── docs/testing/                # 테스트 문서
    ├── TESTING_GUIDE.md         # 이 파일
    └── BOOKMARK_TEST_GUIDE.md   # 북마크 테스트 상세 가이드
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 자동 환경 설정
python scripts/test/setup_dev_environment.py

# 수동 환경 설정
cp env.example .env
# .env 파일 편집 후
docker-compose -f docker/test/docker-compose.test.yml up -d
pipenv install --dev
```

### 2. 기본 테스트 실행

```bash
# 전체 단위 테스트
pytest tests/ -v

# 수동 테스트
python tests/manual/consumer_test.py
python tests/manual/task_test.py

# 성능 테스트
python tests/performance/bookmark_performance_test.py
```

## 📋 테스트 유형별 가이드

### 🔧 단위 테스트 (Unit Tests)

**목적**: 개별 함수/클래스의 기능 검증

```bash
# 전체 단위 테스트
pytest tests/ -v

# 특정 모듈 테스트
pytest tests/tasks/test_bookmark_save_task.py -v
pytest tests/consumers/test_bookmark_save_rmq.py -v

# 커버리지 포함
pytest --cov=app --cov-report=html tests/
```

**주요 테스트 항목**:
- BookmarkData 클래스 생성 및 검증
- Consumer 메시지 파싱 및 검증
- Task 비즈니스 로직
- 오류 처리 및 예외 상황

### 🧪 수동 테스트 (Manual Tests)

**목적**: 실제 환경에서의 동작 검증

#### Consumer 테스트
```bash
python tests/manual/consumer_test.py
```

**테스트 내용**:
- 정상적인 메시지 처리
- 필수 필드 누락 처리
- 잘못된 데이터 타입 처리
- JSON 파싱 오류 처리

#### Task 테스트
```bash
python tests/manual/task_test.py
```

**테스트 내용**:
- BookmarkData 생성 및 검증
- 데이터 변환 (Consumer → Task)
- 컴포넌트 함수 import
- 특수 문자 및 긴 데이터 처리

### 🔗 통합 테스트 (Integration Tests)

**목적**: 전체 시스템 플로우 검증

```bash
# 통합 테스트 실행
pytest tests/integration/ -v

# 특정 통합 테스트
pytest tests/integration/test_bookmark_flow_integration.py -v
```

**테스트 시나리오**:
- Consumer → Celery → Task 전체 플로우
- 유사 북마크 있는/없는 경우
- 외부 서비스 오류 상황
- 대량 데이터 처리

### ⚡ 성능 테스트 (Performance Tests)

**목적**: 시스템 성능 및 확장성 검증

```bash
python tests/performance/bookmark_performance_test.py
```

**측정 항목**:
- 처리량 (메시지/초)
- 응답 시간 (평균, 중간값, 최대/최소)
- 메모리 사용량
- 동시 처리 성능
- RabbitMQ 전송 성능

## 🛠️ 실제 환경 테스트

### 1. 로컬 개발 환경

```bash
# 1. 인프라 서비스 시작
docker-compose -f docker/test/docker-compose.test.yml up -d

# 2. Consumer 시작 (터미널 1)
pipenv run python -m app.consumers.bookmark_save_rmq

# 3. Celery Worker 시작 (터미널 2)
pipenv run celery -A app.core.celery_worker worker --loglevel=info -Q embedding

# 4. 테스트 실행 (터미널 3)
python tests/manual/consumer_test.py
```

### 2. 전체 플로우 테스트

```bash
# RabbitMQ 메시지 전송으로 전체 플로우 테스트
python -c "
import asyncio
import json
from app.core.rabbit import get_rabbit_connection
import aio_pika

async def send_test_message():
    connection = await get_rabbit_connection()
    channel = await connection.channel()
    
    test_data = {
        'userId': 123,
        'starId': 'full_flow_test',
        's3Key': 'test/full_flow.html',
        'title': '전체 플로우 테스트',
        'url': 'https://example.com/full-flow',
        'keywords': ['전체', '플로우', '테스트'],
        'memo': '전체 플로우 테스트 메모',
        'summary': '전체 플로우를 테스트합니다.'
    }
    
    message = aio_pika.Message(
        json.dumps(test_data).encode('utf-8'),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
    )
    
    await channel.default_exchange.publish(
        message,
        routing_key='nebula.bookmark.save'
    )
    
    print('✅ 테스트 메시지 전송 완료')
    await connection.close()

asyncio.run(send_test_message())
"
```

## 📊 모니터링 및 디버깅

### 1. 로그 모니터링

```bash
# Consumer 로그 (상세)
LOG_LEVEL=DEBUG python -m app.consumers.bookmark_save_rmq

# Celery Worker 로그 (상세)
celery -A app.core.celery_worker worker --loglevel=debug -Q embedding

# 특정 태스크 로그 필터링
celery -A app.core.celery_worker worker --loglevel=info | grep "bookmark"
```

### 2. 서비스 상태 확인

```bash
# Docker 서비스 상태
docker-compose -f docker/test/docker-compose.test.yml ps

# RabbitMQ 관리 UI
# http://localhost:15672 (guest/guest)

# Flower (Celery 모니터링)
celery -A app.core.celery_worker flower
# http://localhost:5555
```

### 3. 큐 상태 확인

```bash
# RabbitMQ 큐 상태 확인
docker exec test-rabbitmq rabbitmqctl list_queues

# 메시지 수 확인
docker exec test-rabbitmq rabbitmqctl list_queues name messages
```

## 🔍 문제 해결

### 일반적인 문제들

#### 1. RabbitMQ 연결 실패
```bash
# 서비스 재시작
docker-compose -f docker/test/docker-compose.test.yml restart rabbitmq

# 로그 확인
docker-compose -f docker/test/docker-compose.test.yml logs rabbitmq

# 포트 확인
netstat -an | grep 5672
```

#### 2. Celery Worker 문제
```bash
# Worker 상태 확인
celery -A app.core.celery_worker inspect active

# Worker 재시작
celery -A app.core.celery_worker control shutdown
celery -A app.core.celery_worker worker --loglevel=info -Q embedding

# 큐 정리
celery -A app.core.celery_worker purge
```

#### 3. 데이터베이스 연결 문제
```bash
# PostgreSQL 상태 확인
docker-compose -f docker/test/docker-compose.test.yml logs postgres

# 데이터베이스 재초기화
python scripts/init_database.py

# 연결 테스트
python scripts/test_db_connection.py
```

#### 4. 메모리 부족
```bash
# 메모리 사용량 확인
docker stats

# 불필요한 컨테이너 정리
docker system prune

# 테스트 데이터 크기 줄이기
# tests/performance/bookmark_performance_test.py에서 test_sizes 수정
```

## 📈 성능 최적화 가이드

### 1. Consumer 최적화

```python
# app/consumers/bookmark_save_rmq.py
# QoS 설정 조정
await channel.set_qos(prefetch_count=10)  # 동시 처리 메시지 수

# 배치 처리 구현
messages = []
async for message in queue:
    messages.append(message)
    if len(messages) >= 10:  # 배치 크기
        await process_batch(messages)
        messages = []
```

### 2. Celery 최적화

```bash
# Worker 수 증가
celery -A app.core.celery_worker worker --concurrency=4 -Q embedding

# 메모리 제한 설정
celery -A app.core.celery_worker worker --max-memory-per-child=200000 -Q embedding

# 태스크 라우팅 최적화
# app/core/celery_worker.py에서 CELERY_TASK_ROUTES 설정
```

### 3. 데이터베이스 최적화

```python
# 벡터 저장 배치 처리
# app/services/vector_service.py
async def save_documents_batch(self, documents: List[Dict]):
    # 배치로 여러 문서 동시 저장
    pass

# 연결 풀 크기 조정
# app/core/database.py
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 10
```

## 📝 테스트 체크리스트

### 개발 전 체크리스트
- [ ] 환경 변수 설정 완료 (.env)
- [ ] Docker 서비스 정상 실행
- [ ] 데이터베이스 초기화 완료
- [ ] 의존성 설치 완료

### 기능 테스트 체크리스트
- [ ] Consumer 메시지 수신 및 파싱
- [ ] 데이터 검증 및 오류 처리
- [ ] Celery 태스크 큐 전달
- [ ] Task 비즈니스 로직 실행
- [ ] 외부 서비스 연동 (S3, 임베딩)
- [ ] 데이터베이스 저장
- [ ] 관계 메시지 발행

### 성능 테스트 체크리스트
- [ ] 단일 메시지 처리 시간 < 100ms
- [ ] 처리량 > 10 메시지/초
- [ ] 메모리 사용량 안정적
- [ ] 동시 처리 성능 확인
- [ ] 대량 데이터 처리 안정성

### 배포 전 체크리스트
- [ ] 모든 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 성능 테스트 기준 충족
- [ ] 로그 레벨 적절히 설정
- [ ] 모니터링 설정 완료

## 🎯 테스트 자동화

### GitHub Actions 설정

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      rabbitmq:
        image: rabbitmq:3-management
        ports:
          - 5672:5672
        options: >-
          --health-cmd "rabbitmqctl status"
          --health-interval 30s
          --health-timeout 10s
          --health-retries 5
      
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 30s
          --health-timeout 10s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install pipenv
        pipenv install --dev
    
    - name: Run unit tests
      run: pipenv run pytest tests/ -v
    
    - name: Run manual tests
      run: |
        pipenv run python tests/manual/consumer_test.py
        pipenv run python tests/manual/task_test.py
    
    - name: Run performance tests
      run: pipenv run python tests/performance/bookmark_performance_test.py
```

### 로컬 테스트 자동화

```bash
# Makefile에 추가
.PHONY: test-all
test-all: test-unit test-manual test-performance

.PHONY: test-unit
test-unit:
	pytest tests/ -v

.PHONY: test-manual
test-manual:
	python tests/manual/consumer_test.py
	python tests/manual/task_test.py

.PHONY: test-performance
test-performance:
	python tests/performance/bookmark_performance_test.py

.PHONY: test-setup
test-setup:
	docker-compose -f docker/test/docker-compose.test.yml up -d
	sleep 10
	python scripts/test/setup_dev_environment.py
```

## 📚 추가 리소스

- [북마크 테스트 상세 가이드](BOOKMARK_TEST_GUIDE.md)
- [수동 테스트 README](../tests/manual/README.md)
- [성능 테스트 결과 분석](performance_analysis.md)
- [트러블슈팅 가이드](troubleshooting.md)

---

**문의사항이나 문제가 발생하면 다음 정보와 함께 이슈를 등록해주세요:**
- 실행 환경 (OS, Python 버전)
- 오류 메시지 및 로그
- 재현 단계
- 기대 결과 vs 실제 결과 