# Nebula AI - NLP 기반 북마크 메모 서비스 인공지능 서버

## 프로젝트 소개
Nebula AI는 웹 페이지의 북마크를 저장하고 분석하여 사용자에게 지능형 검색 및 챗봇 기능을 제공하는 인공지능 서버입니다. 
사용자가 저장한 웹 페이지에서 중요 정보를 추출하고, 벡터 데이터베이스에 저장하여 후속 검색과 질의응답을 가능하게 합니다.

## 주요 기능
- **데이터 추출**: S3에 저장된 HTML 콘텐츠에서 텍스트 및 키워드 추출
- **북마크 저장**: 추출된 데이터를 ChromaDB에 벡터 형태로 저장
- **챗봇 및 검색**: 사용자 질의에 대한 지능형 답변 제공
- **그래프 시각화**: 북마크 간 관계를 키워드 기반으로 시각화

## 아키텍처
Nebula AI는 다음과 같은 구성 요소로 이루어져 있습니다:

- **FastAPI**: 웹 서버 및 API 엔드포인트
- **RabbitMQ**: 메시지 큐를 통한 비동기 작업 처리
- **Celery**: 백그라운드 작업 처리
- **Redis**: 캐싱 및 Celery 결과 저장
- **ChromaDB**: 벡터 데이터베이스 (임베딩 저장)
- **OpenAI API**: 텍스트 임베딩 및 LLM 사용
- **AWS S3**: HTML 콘텐츠 저장

## 프로젝트 구조
```
nebula-ai/
├── app/                       # 애플리케이션 코드
│   ├── __init__.py
│   ├── main.py                # FastAPI 앱 초기화 및 시작점
│   ├── core/                  # 핵심 설정 및 유틸리티
│   │   ├── celery_worker.py   # Celery 작업자 설정
│   │   ├── config.py          # 환경 변수 및 설정
│   │   └── rabbit.py          # RabbitMQ 연결 관리
│   ├── consumers/             # RabbitMQ 메시지 소비자
│   │   ├── bookmark_save_rmq.py  # 북마크 저장 소비자
│   │   ├── chat_request_rmq.py   # 챗봇 요청 소비자
│   │   └── extract_data_rmq.py   # 데이터 추출 소비자
│   ├── services/              # 비즈니스 로직
│   │   ├── chat.py            # 챗봇/검색 관련 기능
│   │   └── extract_data.py    # 데이터 추출 관련 기능
│   ├── tasks/                 # Celery 작업
│   │   └── bookmark_save_task.py  # 북마크 저장 작업
│   ├── utils/                 # 유틸리티 기능
│   │   ├── extract_thumbnail.py  # 썸네일 URL 추출
│   │   └── text_processing.py    # 텍스트 처리 유틸리티
│   └── external/              # 외부 서비스 연동
│       └── s3_service.py      # AWS S3 연동
├── tests/                     # 테스트 코드
│   ├── consumers/             # 소비자 테스트
│   ├── services/              # 서비스 테스트
│   ├── integration/           # 통합 테스트
│   └── conftest.py            # pytest 설정
├── Dockerfile                 # 도커 이미지 빌드 설정
├── docker-compose.yml         # 프로덕션 환경 도커 구성
├── docker-compose.dev.yml     # 개발 환경 도커 구성
├── Pipfile                    # 의존성 관리
├── Pipfile.lock               # 의존성 버전 고정
├── requirements.txt           # pip 요구사항
└── README.md                  # 프로젝트 문서
```

## 데이터 흐름
1. 사용자가 웹 페이지를 북마크하면 HTML이 S3에 저장됩니다.
2. 추출 컨슈머가 HTML에서 텍스트 및 키워드를 추출합니다.
3. 북마크 저장 컨슈머가 처리된 데이터를 ChromaDB에 벡터 형태로 저장합니다.
4. 사용자가 검색이나 질문을 하면 챗봇 컨슈머가 ChromaDB에서 관련 북마크를 찾고 OpenAI API를 사용해 응답합니다.

## 설치 및 실행 방법

### 요구사항
- Docker 및 Docker Compose
- Python 3.12 이상
- OpenAI API 키
- AWS S3 액세스 키

### 환경 변수 설정
`.env` 파일에 다음 변수들을 설정해야 합니다:
```
HUGGINGFACEHUB_API_TOKEN=your_token
EMBEDDING_MODEL_NAME=model_name
MODEL_NAME=model_name
CACHE_DIR=/path/to/cache
OPENAI_API_KEY=your_key
OPENAI_EMBED_MODEL=text-embedding-ada-002
OPENAI_MODEL=gpt-3.5-turbo
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=your_endpoint
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=your_project
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_KEY_ID=your_secret
REGION=ap-northeast-2
BUCKET_NAME=your_bucket
CHROMA_DB_URI=/app/chroma_db
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://redis:6379/0
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
EXTRACT_REQ_QUEUE=extract_request
CHAT_REQ_QUEUE=chat_request
BOOKMARK_SAVE_QUEUE=bookmark_save
BASE_THUMBNAIL=default_thumbnail_url
```

### Docker를 이용한 실행
개발 환경 실행:
```bash
make local
```

프로덕션 환경 실행:
```bash
make start
```

### 서비스 접근
- FastAPI 서버: http://localhost:8000
- RabbitMQ 관리자 콘솔: http://localhost:15672 (guest/guest)
- Flower (Celery 모니터링): http://localhost:5555

## API 엔드포인트
- `/`: 서버 상태 확인 엔드포인트

## 개발 및 테스트

### 테스트 실행
```bash
make test
```

### 테스트 커버리지 측정, html 출력
```bash
make cov-html
```

### 코드 스타일 검사
```bash
make lint
```
