# 🔖 Nebula AI - AI 기반 북마크 관리 & 사용자 프로필 시스템

Nebula AI는 CQRS 패턴 기반의 마이크로서비스 아키텍처로 구축된 AI 기반 북마크 저장 및 사용자 프로필 관리 시스템입니다.

## ✨ 주요 기능

### 🎯 핵심 시스템
- **AI 기반 북마크 저장**: 자동 콘텐츠 분석 및 키워드 추출
- **실시간 프로필 업데이트**: 사용자 행동 기반 프로필 최적화 (Task #32)
- **벡터 유사도 검색**: 768차원 임베딩 기반 콘텐츠 매칭
- **RAG 기반 채팅**: 북마크 기반 맞춤형 AI 대화
- **CQRS 아키텍처**: 읽기/쓰기 분리로 최적화된 성능

### 🚀 최신 업데이트 (Task #32 - 프로필 업데이트 시스템 최적화)
- ✅ **실시간 북마크 프로필 업데이트**: 북마크 저장 시 즉시 프로필 갱신
- ✅ **실시간 채팅 세션 프로필 업데이트**: 채팅 완료 시 프로필 반영
- ✅ **일일 프로필 품질 모니터링**: 자동 품질 검사 및 업데이트
- ✅ **CQRS API 통합**: ProfileAPIAdapter를 통한 완전한 통합
- 🔄 **주간 전체 재계산**: 머신러닝 기반 배치 시스템 (개발 예정)

---

## 🚀 빠른 시작

### 환경 설정
```bash
# 프로젝트 클론
git clone <repository-url>
cd nebula-ai

# 의존성 설치
make install

# 환경 변수 설정
cp env.example .env
# .env 파일 편집 (API 키 등 설정)

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
make test-integration # 통합 테스트

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

---

## 📂 시스템 아키텍처

### 전체 구성도
```
┌─────────────────┐    HTTP API    ┌─────────────────┐
│   Spring Boot   │ ──────────────► │   AI Server     │
│    서버         │                │  (FastAPI)      │
│                 │                │                 │
│ - 사용자 인증   │                │ - 프로필 분석   │
│ - 웹 인터페이스 │                │ - 추천 엔진     │
│ - 데이터 관리   │                │ - 벡터 처리     │
└─────────────────┘                └─────────────────┘
                                            │
                                     RabbitMQ 큐
                                            ▼
                   ┌─────────────────────────────────────────────┐
                   │         Celery 백그라운드 처리              │
                   │  • 벡터 생성     • 유사도 계산             │
                   │  • 프로필 업데이트 • 추천 생성             │
                   └─────────────────────────────────────────────┘
                                            ▼
                   ┌─────────────────────────────────────────────┐
                   │            데이터 저장소                    │
                   │  • PostgreSQL (메인)  • Redis (캐시)      │
                   │  • Chroma (벡터)      • S3 (파일)         │
                   └─────────────────────────────────────────────┘
```

### 프로젝트 구조

```
nebula-ai/
├── app/                         # 메인 애플리케이션
│   ├── adapters/               # CQRS 어댑터
│   │   └── profile_api_adapter.py # 프로필 API 통합
│   ├── consumers/              # RabbitMQ Consumer
│   │   ├── bookmark_save_rmq.py
│   │   └── extract_data_rmq.py
│   ├── tasks/                  # Celery Task
│   │   ├── bookmark_save_task.py
│   │   ├── user_profile_tasks.py
│   │   └── daily_profile_monitor.py
│   ├── services/               # 비즈니스 로직
│   │   ├── user_profile_processor.py # 프로필 업데이트 엔진
│   │   ├── vector_generator.py
│   │   ├── chat_service.py
│   │   └── message_handlers.py
│   ├── routers/                # FastAPI 라우터
│   │   ├── profile.py          # 사용자 프로필 API
│   │   └── chat_stream.py      # 채팅 스트림 API
│   ├── models/                 # 데이터 모델
│   ├── repositories/           # 데이터 접근 계층
│   └── core/                   # 핵심 설정
├── tests/                      # 테스트 코드
│   ├── manual/                 # 수동 테스트 스크립트
│   ├── performance/            # 성능 테스트
│   ├── integration/            # 통합 테스트
│   └── unit/                   # 단위 테스트
├── docs/                       # 문서
│   ├── architecture.md         # 시스템 아키텍처
│   ├── api_reference.md        # API 참조 문서
│   ├── data_models.md          # 데이터 모델
│   ├── user_profile_update_process.md # 프로필 업데이트 프로세스
│   ├── bookmark_workflow.md    # 북마크 워크플로우
│   ├── chat_api_guide.md       # 채팅 API 가이드
│   ├── text_processing_strategy.md # 텍스트 처리 전략
│   └── testing/                # 테스트 가이드
│       ├── TESTING_GUIDE.md
│       └── BOOKMARK_TEST_GUIDE.md
├── scripts/                    # 유틸리티 스크립트
└── docker/                     # Docker 설정
```

---

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

---

## 🛠️ 개발 가이드

### 로컬 개발 환경
```bash
# 1. 인프라 서비스 시작
docker-compose -f docker/test/docker-compose.test.yml up -d

# 2. AI 서버 시작 (터미널 1)
pipenv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Consumer 시작 (터미널 2)
pipenv run python -m app.consumers.bookmark_save_rmq

# 4. Celery Worker 시작 (터미널 3)
pipenv run celery -A app.core.celery_worker worker --loglevel=info -Q embedding

# 5. 테스트 실행 (터미널 4)
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

---

## 📊 모니터링

### 서비스 모니터링
- **RabbitMQ 관리 UI**: http://localhost:15672 (guest/guest)
- **Flower (Celery)**: http://localhost:5555
- **FastAPI Docs**: http://localhost:8000/docs
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

---

## 🎯 주요 기능 플로우

### 1. 북마크 저장 플로우 (3단계)

#### 1단계: AI 서버의 일차 키워드 추출
```mermaid
graph TD
    A[사용자 URL 제출] --> B[HTML 다운로드]
    B --> C[텍스트 추출]
    C --> D[형태소 분석]
    D --> E[키워드 추출]
    E --> F[사용자에게 키워드 제안]
```

#### 2단계: 사용자의 최종 선택
- AI 제안 키워드 중 선택/수정
- 개인 메모 작성
- 요약 확인/수정

#### 3단계: AI 서버의 저장 처리
```mermaid
graph TD
    A[RabbitMQ 메시지 수신] --> B[사용자 설정 정보 활용]
    B --> C[RAG 최적화 청크 분할]
    C --> D[벡터 임베딩 생성]
    D --> E[PostgreSQL 저장]
    E --> F[프로필 업데이트 트리거]
```

### 2. 실시간 프로필 업데이트 플로우 (Task #32)

```mermaid
sequenceDiagram
    participant U as 사용자 행동
    participant L as EventListener
    participant P as ProfileProcessor
    participant A as APIAdapter
    participant Q as RabbitMQ
    participant D as Database

    U->>L: 북마크 저장/채팅 완료
    L->>P: 이벤트 처리
    P->>A: API 어댑터 호출
    A->>Q: 메시지 발행
    Q->>P: 백그라운드 처리
    P->>D: 프로필 업데이트
```

### 3. RAG 기반 채팅 플로우

```mermaid
graph TD
    A[사용자 질문] --> B[벡터 유사도 검색]
    B --> C[관련 북마크 검색]
    C --> D[컨텍스트 구성]
    D --> E[OpenAI GPT 호출]
    E --> F[스트리밍 응답]
    F --> G[채팅 세션 저장]
    G --> H[프로필 업데이트]
```

---

## 📈 성능 특징

### 처리 성능
- **북마크 처리량**: 10+ 메시지/초
- **API 응답시간**: 평균 < 100ms (Consumer)
- **벡터 검색**: < 50ms (1000+ 벡터 기준)
- **프로필 업데이트**: 실시간 (< 200ms)

### 확장성
- **수평적 확장**: Celery Worker 독립 스케일링
- **캐시 최적화**: Redis 다층 캐싱
- **데이터베이스**: pgvector 인덱스 최적화
- **메시지 큐**: RabbitMQ 클러스터 지원

---

## 🔧 문제 해결

### 일반적인 문제들
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

---

## 📚 문서

### 시스템 문서
- [시스템 아키텍처](docs/architecture.md) - 전체 시스템 구조
- [API 참조 문서](docs/api_reference.md) - 모든 API 엔드포인트
- [데이터 모델](docs/data_models.md) - 데이터베이스 스키마

### 프로세스 문서
- [사용자 프로필 업데이트 프로세스](docs/user_profile_update_process.md) - Task #32 구현
- [북마크 워크플로우](docs/bookmark_workflow.md) - 3단계 저장 프로세스
- [채팅 API 가이드](docs/chat_api_guide.md) - RAG 기반 채팅
- [텍스트 처리 전략](docs/text_processing_strategy.md) - NLP 처리 방식

### 개발 문서
- [테스트 가이드](docs/testing/TESTING_GUIDE.md) - 완전한 테스트 가이드
- [북마크 테스트 가이드](docs/testing/BOOKMARK_TEST_GUIDE.md) - 북마크 기능 테스트

---

## 🔑 환경 변수 설정

### 필수 설정
```bash
# OpenAI API
OPENAI_API_KEY=your_openai_api_key
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_MODEL=gpt-4o-mini

# Anthropic API (Claude)
ANTHROPIC_API_KEY=your_anthropic_api_key

# 데이터베이스
DATABASE_URL=postgresql://user:password@localhost:5432/nebula_ai
REDIS_URL=redis://localhost:6379/0
CHROMA_DB_URI=http://localhost:8000

# 메시지 큐
RABBITMQ_URL=amqp://guest:guest@localhost:5672//

# AWS S3
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_KEY_ID=your_aws_secret_key
BUCKET_NAME=your_s3_bucket
```

---

## 🚢 배포

### 개발 환경
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 프로덕션 환경
```bash
docker-compose up -d
```

---

## 🤝 기여하기

1. 이슈 확인 또는 새 이슈 생성
2. 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 생성

### 기여 전 체크리스트
- [ ] 모든 테스트 통과 (`make test-all`)
- [ ] Lint 검사 통과 (`make lint`)
- [ ] 커버리지 80% 이상 (`make test-cov`)
- [ ] 문서 업데이트 (필요 시)

---

## 📜 라이선스

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🏗️ 향후 계획

### 단기 (3개월)
- [ ] 추천 엔진 고도화 (Task #3 - 협업 필터링 + 콘텐츠 기반)
- [ ] A/B 테스트 프레임워크 (Task #8)
- [ ] 성능 메트릭 대시보드

### 중기 (6개월)
- [ ] 컨텍스트 기반 추천 시스템 (Task #16)
- [ ] 주제별 학습 경로 추천 (Task #17)
- [ ] 시간 적응형 추천 (Task #18)

### 장기 (1년)
- [ ] 자체 ML 모델 훈련
- [ ] 실시간 개인화 엔진
- [ ] 다중 테넌트 지원

---

## 📞 지원

문제가 발생하거나 질문이 있으시면:

1. [Issues](https://github.com/your-repo/issues)에서 기존 이슈 확인
2. 새로운 이슈 생성
3. [Discussions](https://github.com/your-repo/discussions)에서 토론

**Happy Coding! 🚀**
