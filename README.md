# 🔖 Nebula AI - 북마크 저장 시스템

AI 기반 북마크 저장 및 관리 시스템입니다.

## 🚀 빠른 시작

### 환경 설정
```bash
# 의존성 설치
make install

# 환경 변수 설정
cp env.example .env
# .env 파일 편집

# 개발 환경 시작
make local
```

### 테스트 실행
```bash
# 모든 테스트 실행
make test-all

# 개별 테스트 실행
make test-unit        # 단위 테스트
make test-manual      # 수동 테스트
make test-performance # 성능 테스트

# 테스트 환경 설정
make test-setup

# 테스트 도움말
make test-help
```

### 커버리지 테스트
```bash
# 커버리지와 함께 테스트 실행
make test-cov

# HTML 커버리지 리포트 생성 및 열기
make cov-html

# 커버리지 파일 정리
make clean-cov
```

### 특정 테스트 실행 (pytest 직접 사용)
```bash
# 서비스 테스트만 실행
pytest tests/services/ -v

# 프로필 관련 테스트만 실행
pytest tests/ -k "profile" -v

# 통합 테스트만 실행
pytest tests/integration/ -v

# 특정 테스트 파일 실행
pytest tests/services/test_vector_generator.py -v
```

### 테스트 환경 관리
```bash
# 테스트 서비스 상태 확인
make test-services

# 테스트 서비스 로그 확인
make test-logs

# 테스트 환경 정리
make test-clean
```

## 📂 프로젝트 구조

```
nebula-ai/
├── app/                         # 메인 애플리케이션
│   ├── consumers/               # RabbitMQ Consumer
│   ├── tasks/                   # Celery Task
│   ├── services/                # 비즈니스 로직
│   └── ...
├── tests/                       # 테스트 코드
│   ├── manual/                  # 수동 테스트 스크립트
│   ├── performance/             # 성능 테스트
│   ├── integration/             # 통합 테스트
│   └── unit/                    # 단위 테스트
├── scripts/test/                # 테스트 설정 스크립트
├── docker/test/                 # 테스트용 Docker 설정
├── docs/testing/                # 테스트 문서
│   ├── TESTING_GUIDE.md         # 완전한 테스트 가이드
│   └── BOOKMARK_TEST_GUIDE.md   # 북마크 테스트 상세 가이드
└── ...
```

## 🧪 테스트 가이드

### 빠른 테스트
```bash
# 1. 테스트 환경 설정
make test-setup

# 2. 기본 테스트 실행
make test-unit

# 3. 수동 테스트 (실제 동작 확인)
make test-manual
```

### 상세 테스트 가이드
- [완전한 테스트 가이드](docs/testing/TESTING_GUIDE.md)
- [북마크 테스트 상세 가이드](docs/testing/BOOKMARK_TEST_GUIDE.md)
- [수동 테스트 README](tests/manual/README.md)

### 테스트 유형
- **단위 테스트**: 개별 함수/클래스 검증
- **수동 테스트**: 실제 환경에서의 동작 검증
- **통합 테스트**: 전체 시스템 플로우 검증
- **성능 테스트**: 처리량, 응답시간, 메모리 사용량 측정

## 🛠️ 개발 가이드

### 로컬 개발 환경
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

### 코드 품질
```bash
# Lint 검사
make lint

# 테스트 커버리지
make test-cov

# 커버리지 HTML 보고서
make cov-html
```

## 📊 모니터링

### 서비스 모니터링
- **RabbitMQ 관리 UI**: http://localhost:15672 (guest/guest)
- **Flower (Celery)**: http://localhost:5555
- **테스트 서비스 상태**: `make test-services`

### 로그 확인
```bash
# 테스트 서비스 로그
make test-logs

# Consumer 로그 (상세)
LOG_LEVEL=DEBUG python -m app.consumers.bookmark_save_rmq

# Celery Worker 로그 (상세)
celery -A app.core.celery_worker worker --loglevel=debug
```

## 🎯 주요 기능

### 북마크 저장 플로우
1. **메시지 수신**: RabbitMQ Consumer가 북마크 저장 요청 수신
2. **데이터 검증**: 필수 필드 및 데이터 타입 검증
3. **백그라운드 처리**: Celery Task로 비동기 처리
4. **콘텐츠 추출**: S3에서 HTML 다운로드 및 텍스트 추출
5. **유사도 계산**: 기존 북마크와의 유사도 계산
6. **벡터 저장**: 임베딩 생성 및 벡터 데이터베이스 저장
7. **관계 생성**: 유사한 북마크 관계 메시지 발행

### 성능 특징
- **처리량**: 10+ 메시지/초
- **응답시간**: 평균 < 100ms (Consumer)
- **확장성**: 수평적 확장 가능 (Worker 추가)
- **안정성**: 자동 재시도 및 오류 처리

## 🔧 문제 해결

### 일반적인 문제
```bash
# RabbitMQ 연결 실패
make test-services
docker-compose -f docker/test/docker-compose.test.yml restart rabbitmq

# Celery Worker 문제
celery -A app.core.celery_worker inspect active
celery -A app.core.celery_worker purge

# 테스트 환경 초기화
make test-clean
make test-setup
```

### 도움말
```bash
# 테스트 명령어 도움말
make test-help

# 전체 Makefile 명령어
make help
```

## 📚 문서

- [테스트 가이드](docs/testing/TESTING_GUIDE.md)
- [북마크 테스트 가이드](docs/testing/BOOKMARK_TEST_GUIDE.md)
- [API 문서](docs/api/)
- [아키텍처 문서](docs/architecture/)

## 🤝 기여하기

1. 이슈 확인 또는 새 이슈 생성
2. 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 생성

### 기여 전 체크리스트
- [ ] 모든 테스트 통과 (`make test-all`)
- [ ] Lint 검사 통과 (`make lint`)
- [ ] 테스트 커버리지 유지
- [ ] 문서 업데이트 (필요시)

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📊 테스트 구조

```
tests/
├── services/          # 서비스 레이어 테스트
│   ├── test_vector_generator.py
│   ├── test_user_profile_processor.py
│   ├── test_message_handlers.py
│   └── test_chat_service.py
├── schemas/           # Pydantic 스키마 테스트
│   ├── test_profile_schemas.py
│   └── test_chat_schemas.py
├── routers/           # API 라우터 테스트
│   ├── test_profile_api.py
│   └── test_chat_stream.py
├── integration/       # 통합 테스트
│   ├── test_profile_integration.py
│   └── test_bookmark_flow_integration.py
├── models/           # 데이터베이스 모델 테스트
├── manual/           # 수동 테스트 스크립트
├── performance/      # 성능 테스트
└── conftest.py       # 공통 테스트 설정
```
