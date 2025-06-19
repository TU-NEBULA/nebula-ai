# 📋 수동 테스트 (Manual Tests)

이 디렉토리는 북마크 저장 시스템의 수동 테스트 스크립트들을 포함합니다.

## 📂 파일 구조

```
tests/manual/
├── README.md                    # 이 파일
├── manual_bookmark_test.py      # 메인 수동 테스트 스크립트
├── consumer_test.py             # Consumer 단독 테스트
├── task_test.py                 # Task 단독 테스트
├── rabbitmq_test.py             # RabbitMQ 연결 테스트
└── performance_test.py          # 간단한 성능 테스트
```

## 🚀 빠른 시작

### 기본 테스트 실행
```bash
# 메인 테스트 스크립트 실행
python tests/manual/manual_bookmark_test.py

# 개별 컴포넌트 테스트
python tests/manual/consumer_test.py
python tests/manual/task_test.py
python tests/manual/rabbitmq_test.py
```

### 환경 설정
```bash
# 개발 환경 자동 설정
python scripts/test/setup_dev_environment.py

# 테스트용 Docker 서비스 시작
docker-compose -f docker/test/docker-compose.test.yml up -d
```

## 📊 테스트 옵션

### 1. 전체 플로우 테스트
- Consumer → Task → 데이터베이스 저장
- RabbitMQ 메시지 큐 통신
- 유사도 계산 및 관계 생성

### 2. 개별 컴포넌트 테스트
- Consumer 메시지 처리 테스트
- Task 비즈니스 로직 테스트
- RabbitMQ 연결 및 메시지 전송 테스트

### 3. 성능 테스트
- 대량 메시지 처리 테스트
- 동시 처리 성능 테스트
- 메모리 사용량 모니터링

## 🔧 트러블슈팅

### 일반적인 문제들
1. **RabbitMQ 연결 실패**: `docker/test/docker-compose.test.yml`로 서비스 시작
2. **모듈 import 오류**: 프로젝트 루트에서 실행 확인
3. **환경변수 오류**: `.env` 파일 설정 확인

### 로그 확인
```bash
# 상세 로그로 실행
LOG_LEVEL=DEBUG python tests/manual/manual_bookmark_test.py

# Consumer 로그 확인
python -m app.consumers.bookmark_save_rmq

# Celery Worker 로그 확인
celery -A app.core.celery_worker worker --loglevel=debug
```

## 📝 테스트 결과 예시

### 성공적인 테스트 출력
```
✅ Consumer 테스트 완료
✅ BookmarkData 생성 성공
✅ 메시지 전송 완료: nebula.bookmark.save
```

### 예상되는 경고
```
⚠️ pgvector가 설치되지 않았습니다. 벡터 검색 기능이 비활성화됩니다.
📝 참고: 실제 태스크 실행은 Celery Worker에서 별도 프로세스로 처리됩니다.
```

이러한 경고들은 정상적이며 실제 운영환경에서는 문제가 되지 않습니다. 