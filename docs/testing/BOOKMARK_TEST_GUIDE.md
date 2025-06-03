# 🔖 북마크 저장 시스템 실제 테스트 가이드

이 가이드는 북마크 저장 시스템을 실제로 테스트해볼 수 있는 방법들을 제공합니다.

## 🚀 빠른 시작

### 방법 1: 자동 설정 스크립트 사용

```bash
# 개발 환경 자동 설정
python scripts/setup_dev_environment.py

# 테스트 실행
python scripts/manual_bookmark_test.py
```

### 방법 2: 수동 설정 (단계별)

#### 1단계: 인프라 서비스 시작

```bash
# 테스트용 Docker 서비스 시작
docker-compose -f docker-compose.test.yml up -d

# 서비스 상태 확인
docker-compose -f docker-compose.test.yml ps
```

#### 2단계: 환경 설정

```bash
# 환경 파일 복사
cp env.example .env

# .env 파일 편집 (필요한 API 키들 설정)
# - OPENAI_API_KEY (임베딩용)
# - AWS 설정 (S3 사용시)
```

#### 3단계: 의존성 설치

```bash
# Python 의존성 설치
pipenv install --dev

# 환경 활성화
pipenv shell
```

#### 4단계: 데이터베이스 초기화

```bash
# 데이터베이스 테이블 생성
python scripts/init_database.py
```

#### 5단계: 서비스 시작 (각각 별도 터미널에서)

```bash
# 터미널 1: Consumer 시작
pipenv run python -m app.consumers.bookmark_save_rmq

# 터미널 2: Celery Worker 시작
pipenv run celery -A app.core.celery_worker worker --loglevel=info -Q embedding

# 터미널 3: 테스트 실행
pipenv run python scripts/manual_bookmark_test.py
```

## 🧪 테스트 방법들

### 1. 전체 플로우 테스트

```bash
python scripts/manual_bookmark_test.py
```

선택 옵션:
1. **RabbitMQ 메시지 전송** - 실제 메시지 큐를 통한 전체 플로우
2. **Consumer 단독 테스트** - Consumer 로직만 테스트
3. **Task 직접 실행** - Celery Task 직접 호출
4. **모든 방법 테스트** - 위 모든 방법 순차 실행

### 2. 개별 컴포넌트 테스트

#### Consumer만 테스트
```python
import asyncio
from app.consumers.bookmark_save_rmq import on_bookmark_save

# 테스트 메시지 생성 및 전송
# (scripts/manual_bookmark_test.py 참고)
```

#### Task만 테스트
```python
from app.tasks.bookmark_save_task import save_bookmark_task

# 북마크 데이터로 직접 호출
bookmark_data = {"userId": 123, ...}
result = save_bookmark_task(bookmark_data)
```

### 3. API를 통한 테스트

FastAPI 서버가 실행 중이라면:

```bash
curl -X POST "http://localhost:8000/api/v1/bookmark/save" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": 123,
    "starId": "api_test_001",
    "title": "API 테스트 북마크",
    "url": "https://example.com/api-test",
    "keywords": ["API", "테스트"],
    "memo": "API를 통한 테스트",
    "summary": "FastAPI를 통한 북마크 저장 테스트"
  }'
```

## 🔍 모니터링 및 디버깅

### RabbitMQ 관리 웹UI
- URL: http://localhost:15672
- 계정: guest/guest
- 큐 상태, 메시지 수 확인 가능

### Flower (Celery 모니터링)
```bash
# Flower 시작
docker-compose -f docker-compose.test.yml --profile monitoring up -d flower

# 웹UI 접속
# URL: http://localhost:5555
```

### 로그 확인
```bash
# Consumer 로그
pipenv run python -m app.consumers.bookmark_save_rmq

# Celery Worker 로그
pipenv run celery -A app.core.celery_worker worker --loglevel=debug

# Docker 서비스 로그
docker-compose -f docker-compose.test.yml logs -f [서비스명]
```

## 🛠️ 문제 해결

### 일반적인 문제들

#### 1. RabbitMQ 연결 실패
```bash
# 서비스 상태 확인
docker-compose -f docker-compose.test.yml ps

# 로그 확인
docker-compose -f docker-compose.test.yml logs rabbitmq

# 재시작
docker-compose -f docker-compose.test.yml restart rabbitmq
```

#### 2. 데이터베이스 연결 실패
```bash
# PostgreSQL 상태 확인
docker-compose -f docker-compose.test.yml logs postgres

# 데이터베이스 재초기화
python scripts/init_database.py
```

#### 3. S3 관련 오류
- AWS 자격 증명 확인
- S3 버킷 접근 권한 확인
- 로컬 파일로 테스트 (S3 키 대신 로컬 파일 경로 사용)

#### 4. 임베딩 모델 오류
- OpenAI API 키 확인
- 네트워크 연결 확인
- 다른 모델로 변경 시도

### 로그 레벨 조정
```python
# .env 파일에서
DEBUG=true
LOG_LEVEL=DEBUG
```

## 📊 성능 테스트

### 대량 메시지 테스트
```python
# scripts/manual_bookmark_test.py를 수정하여
# 여러 개의 북마크를 동시에 전송
for i in range(10):
    bookmark_data = get_sample_bookmark_data()
    bookmark_data['starId'] = f'batch_test_{i}'
    await send_bookmark_message(bookmark_data)
```

### 유사도 계산 성능 테스트
```python
# 큰 텍스트로 테스트
# 많은 기존 북마크가 있는 상황에서 테스트
```

## 🎯 실제 사용 시나리오

### 시나리오 1: 웹 페이지 북마크
1. HTML 파일을 S3에 업로드
2. 북마크 메시지 전송
3. 텍스트 추출 및 임베딩 생성
4. 유사한 북마크 찾기
5. 관계 메시지 발행

### 시나리오 2: 메모가 있는 북마크
1. 북마크 + 사용자 메모
2. 메모도 함께 벡터화
3. 관련 북마크 추천

### 시나리오 3: 키워드 기반 북마크
1. 사전 정의된 키워드
2. 키워드 기반 분류
3. 카테고리별 관계 생성

## 📝 테스트 체크리스트

- [ ] 인프라 서비스 정상 시작
- [ ] Consumer 메시지 수신 확인
- [ ] Celery Task 실행 확인
- [ ] S3 파일 다운로드 확인
- [ ] 텍스트 추출 확인
- [ ] 임베딩 생성 확인
- [ ] 유사도 계산 확인
- [ ] 데이터베이스 저장 확인
- [ ] 관계 메시지 발행 확인
- [ ] 오류 처리 확인

## 🔧 고급 설정

### 커스텀 유사도 임계값
```python
# app/config.py에서
SIMILARITY_THRESHOLD = 0.8  # 기본값 조정
```

### 배치 처리 크기 조정
```python
# Celery 설정에서
CELERY_TASK_ROUTES = {
    'bookmark_save_task': {'queue': 'embedding', 'rate_limit': '10/m'}
}
```

### 벡터 데이터베이스 설정
```python
# ChromaDB 설정
CHROMA_COLLECTION_NAME = "bookmarks_test"
CHROMA_EMBEDDING_FUNCTION = "openai"  # 또는 "huggingface"
```

---

문제가 발생하면 GitHub Issues에 다음 정보와 함께 문의해주세요:
- 오류 메시지
- 실행 환경 (OS, Python 버전)
- 로그 파일
- 테스트 시나리오 