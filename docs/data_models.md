# Nebula AI 데이터 모델 문서

## 개요

Nebula AI 시스템의 데이터 모델은 사용자 프로필, 북마크, 벡터 데이터, 추천 정보 등을 체계적으로 관리하기 위해 설계되었습니다. PostgreSQL을 메인 데이터베이스로 사용하며, 벡터 유사도 검색을 위한 특화된 구조를 포함합니다.

## 데이터베이스 구성

### 메인 데이터베이스 (PostgreSQL)
- **목적**: 구조화된 데이터 저장 및 관리
- **확장**: pgvector (벡터 연산 지원)
- **버전**: PostgreSQL 15+

### 캐시 레이어 (Redis)
- **목적**: 고속 캐싱 및 세션 관리
- **구조**: Key-Value 저장소
- **TTL**: 데이터 타입별 만료 시간 설정

### 벡터 데이터베이스 (Chroma)
- **목적**: 고성능 벡터 유사도 검색
- **차원**: 768차원 (OpenAI text-embedding-3-small)

---

## 핵심 데이터 모델

### 1. UserProfile (사용자 프로필)

사용자의 관심사와 행동 패턴을 벡터로 표현한 핵심 모델입니다.

```python
class UserProfile(BaseModel):
    """사용자 프로필 모델"""
    
    # 기본 정보
    user_id: int                    # 사용자 식별자 (Primary Key)
    created_at: datetime            # 생성 시간
    updated_at: datetime            # 마지막 업데이트 시간
    
    # 프로필 벡터 (768차원)
    profile_vector: List[float]     # 사용자 관심사 벡터
    vector_strength: float          # 벡터 강도 (0.0-1.0)
    vector_metadata: Dict[str, Any] # 벡터 메타데이터
    
    # 품질 지표
    completeness_score: float       # 완성도 점수 (0.0-1.0)
    quality_score: float            # 전체 품질 점수 (0.0-1.0)
    activity_level: float           # 활동 수준 (0.0-1.0)
    diversity_score: float          # 관심사 다양성 (0.0-1.0)
    recency_score: float            # 최신성 점수 (0.0-1.0)
    
    # 업데이트 관련
    update_count: int               # 업데이트 횟수
    last_similarity_update: datetime # 마지막 유사도 계산 시간
    next_scheduled_update: datetime  # 다음 업데이트 예정 시간
```

**테이블 스키마 (PostgreSQL)**
```sql
CREATE TABLE user_profiles (
    user_id INTEGER PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 벡터 데이터 (pgvector 확장 사용)
    profile_vector vector(768),
    vector_strength FLOAT DEFAULT 0.0,
    vector_metadata JSONB DEFAULT '{}',
    
    -- 품질 지표
    completeness_score FLOAT DEFAULT 0.0,
    quality_score FLOAT DEFAULT 0.0,
    activity_level FLOAT DEFAULT 0.0,
    diversity_score FLOAT DEFAULT 0.0,
    recency_score FLOAT DEFAULT 0.0,
    
    -- 업데이트 관련
    update_count INTEGER DEFAULT 0,
    last_similarity_update TIMESTAMP WITH TIME ZONE,
    next_scheduled_update TIMESTAMP WITH TIME ZONE
);

-- 벡터 유사도 검색을 위한 인덱스
CREATE INDEX user_profiles_vector_idx ON user_profiles 
USING ivfflat (profile_vector vector_cosine_ops) WITH (lists = 100);
```

### 2. Bookmark (북마크)

사용자가 저장한 북마크와 관련 메타데이터를 저장합니다.

```python
class Bookmark(BaseModel):
    """북마크 모델"""
    
    # 기본 정보
    bookmark_id: str                # 북마크 식별자 (UUID)
    user_id: int                    # 소유자 사용자 ID
    created_at: datetime            # 생성 시간
    updated_at: datetime            # 업데이트 시간
    
    # 북마크 정보
    title: str                      # 사용자 설정 제목
    original_title: str             # 원본 웹페이지 제목
    url: str                        # 원본 URL
    s3_key: str                     # S3 저장된 HTML 파일 키
    
    # 사용자 생성 콘텐츠
    keywords: List[str]             # 사용자 선택 키워드
    memo: Optional[str]             # 사용자 메모
    summary: Optional[str]          # 사용자 확인 요약
    
    # AI 분석 결과
    extracted_text: str             # 추출된 텍스트
    ai_keywords: List[str]          # AI 추출 키워드
    ai_summary: str                 # AI 생성 요약
    
    # 벡터 데이터
    content_vector: List[float]     # 콘텐츠 벡터 (768차원)
    embedding_model: str            # 사용된 임베딩 모델
    
    # 분류 및 태그
    category: Optional[str]         # 카테고리
    tags: List[str]                 # 태그 목록
    domain: str                     # URL 도메인
    
    # 처리 상태
    processing_status: str          # pending, processed, failed
    error_message: Optional[str]    # 오류 메시지 (실패 시)
```

**테이블 스키마**
```sql
CREATE TABLE bookmarks (
    bookmark_id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_profiles(user_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 북마크 정보
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    url TEXT NOT NULL,
    s3_key VARCHAR(500),
    
    -- 사용자 콘텐츠
    keywords TEXT[],
    memo TEXT,
    summary TEXT,
    
    -- AI 분석 결과
    extracted_text TEXT,
    ai_keywords TEXT[],
    ai_summary TEXT,
    
    -- 벡터 데이터
    content_vector vector(768),
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    
    -- 분류 및 태그
    category VARCHAR(100),
    tags TEXT[],
    domain VARCHAR(255),
    
    -- 처리 상태
    processing_status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT
);

-- 인덱스
CREATE INDEX bookmarks_user_id_idx ON bookmarks(user_id);
CREATE INDEX bookmarks_content_vector_idx ON bookmarks 
USING ivfflat (content_vector vector_cosine_ops) WITH (lists = 100);
CREATE INDEX bookmarks_domain_idx ON bookmarks(domain);
CREATE INDEX bookmarks_created_at_idx ON bookmarks(created_at);
```

### 3. BookmarkSimilarity (북마크 유사도)

북마크 간의 유사도 관계를 저장합니다.

```python
class BookmarkSimilarity(BaseModel):
    """북마크 유사도 모델"""
    
    id: int                         # Primary Key
    bookmark_id: str                # 기준 북마크 ID
    similar_bookmark_id: str        # 유사한 북마크 ID
    similarity_score: float         # 유사도 점수 (0.0-1.0)
    similarity_type: str            # content, keyword, semantic
    created_at: datetime            # 계산 시간
    
    # 관계 메타데이터
    shared_keywords: List[str]      # 공통 키워드
    shared_domains: bool            # 동일 도메인 여부
    content_overlap: float          # 콘텐츠 중복도
```

### 4. UserActivity (사용자 활동)

사용자의 모든 활동을 이벤트로 추적합니다.

```python
class UserActivity(BaseModel):
    """사용자 활동 모델"""
    
    # 기본 정보
    activity_id: str                # 활동 식별자 (UUID)
    user_id: int                    # 사용자 ID
    timestamp: datetime             # 활동 시간
    
    # 활동 유형
    activity_type: str              # bookmark, chat, search, view
    action: str                     # create, update, delete, view
    
    # 활동 대상
    target_id: Optional[str]        # 대상 객체 ID
    target_type: Optional[str]      # bookmark, profile, recommendation
    
    # 활동 데이터
    activity_data: Dict[str, Any]   # 활동 관련 데이터
    context: Dict[str, Any]         # 컨텍스트 정보
    
    # 분석 정보
    weight: float                   # 활동 가중치 (프로필 업데이트용)
    quality_impact: float           # 품질에 미치는 영향
    processed: bool                 # 처리 완료 여부
```

### 5. ChatSession (채팅 세션)

사용자의 채팅 세션과 대화 내역을 저장합니다.

```python
class ChatSession(BaseModel):
    """채팅 세션 모델"""
    
    # 세션 정보
    session_id: str                 # 세션 식별자 (UUID)
    user_id: int                    # 사용자 ID
    created_at: datetime            # 세션 시작 시간
    updated_at: datetime            # 마지막 활동 시간
    ended_at: Optional[datetime]    # 세션 종료 시간
    
    # 세션 메타데이터
    total_messages: int             # 총 메시지 수
    session_duration: int           # 세션 지속 시간 (초)
    topics_discussed: List[str]     # 논의된 주제들
    
    # 품질 지표
    engagement_score: float         # 참여도 점수
    topic_diversity: float          # 주제 다양성 점수
    session_quality: float          # 세션 품질 점수
    
    # RAG 관련
    bookmarks_referenced: List[str] # 참조된 북마크 ID들
    similarity_searches: int        # 유사도 검색 횟수
    
    # 프라이버시
    anonymized_content: str         # 익명화된 대화 내용
    contains_pii: bool              # 개인정보 포함 여부
```

### 6. Recommendation (추천)

생성된 추천 정보를 캐시하여 저장합니다.

```python
class Recommendation(BaseModel):
    """추천 모델"""
    
    # 기본 정보
    recommendation_id: str          # 추천 식별자 (UUID)
    user_id: int                    # 대상 사용자 ID
    created_at: datetime            # 생성 시간
    expires_at: datetime            # 만료 시간
    
    # 추천 내용
    recommendation_type: str        # content, user, topic, learning_path
    title: str                      # 추천 제목
    description: str                # 추천 설명
    score: float                    # 추천 점수 (0.0-1.0)
    
    # 추천 데이터
    content_data: Dict[str, Any]    # 추천 콘텐츠 데이터
    metadata: Dict[str, Any]        # 추천 메타데이터
    
    # 추천 소스
    source_type: str                # algorithm, collaborative, content_based
    source_data: Dict[str, Any]     # 추천 생성 근거
    
    # 사용자 반응
    viewed: bool                    # 조회 여부
    clicked: bool                   # 클릭 여부
    liked: bool                     # 좋아요 여부
    feedback_score: Optional[float] # 사용자 피드백 점수
```

---

## 메시지 큐 스키마

### RabbitMQ 메시지 구조

#### 1. 북마크 저장 메시지
```json
{
  "type": "bookmark_save",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "userId": 123,
    "starId": "bookmark_uuid",
    "s3Key": "path/to/html",
    "title": "사용자 제목",
    "url": "https://example.com",
    "keywords": ["AI", "ML", "Python"],
    "memo": "사용자 메모",
    "summary": "콘텐츠 요약"
  },
  "metadata": {
    "source": "spring_boot_server",
    "request_id": "req_12345",
    "priority": "normal"
  }
}
```

#### 2. 프로필 업데이트 메시지
```json
{
  "type": "profile_update",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": 123,
    "activity_data": {
      "type": "BOOKMARK",
      "content": "AI 관련 콘텐츠",
      "weight": 1.5,
      "timestamp": "2024-01-15T10:30:00Z"
    },
    "force_recalculation": false
  },
  "metadata": {
    "source": "profile_optimization_system",
    "quality_score": 0.7,
    "trigger": "bookmark_event"
  }
}
```

#### 3. 채팅 요청 메시지
```json
{
  "type": "chat_request",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": 123,
    "session_id": "session_abc123",
    "message": "AI에 대해 알려주세요",
    "context": {
      "include_history": true,
      "max_history": 10,
      "search_similar": true
    }
  },
  "metadata": {
    "source": "web_interface",
    "request_id": "req_67890"
  }
}
```

---

## 벡터 데이터 구조

### 임베딩 벡터 사양

#### 사용자 프로필 벡터
- **차원**: 768
- **모델**: OpenAI text-embedding-3-small
- **정규화**: L2 정규화 적용
- **업데이트**: 가중 평균 방식

#### 북마크 콘텐츠 벡터
- **차원**: 768
- **모델**: OpenAI text-embedding-3-small
- **소스**: 제목 + 요약 + 키워드
- **전처리**: HTML 태그 제거, 특수문자 정리

#### 유사도 계산
```python
# 코사인 유사도 계산
def calculate_similarity(vector_a, vector_b):
    """두 벡터 간의 코사인 유사도 계산"""
    return np.dot(vector_a, vector_b) / (
        np.linalg.norm(vector_a) * np.linalg.norm(vector_b)
    )

# PostgreSQL에서의 벡터 유사도 검색
SELECT user_id, 1 - (profile_vector <=> %s) as similarity_score
FROM user_profiles 
WHERE 1 - (profile_vector <=> %s) > 0.7
ORDER BY profile_vector <=> %s
LIMIT 10;
```

---

## 캐시 구조 (Redis)

### 캐시 키 패턴

#### 사용자 프로필 캐시
```
user:profile:{user_id}                 # 기본 프로필 정보
user:profile:{user_id}:vector          # 프로필 벡터
user:profile:{user_id}:metrics         # 프로필 메트릭
user:profile:{user_id}:last_update     # 마지막 업데이트 시간
```

#### 추천 캐시
```
user:recommendations:{user_id}         # 사용자 추천 목록
user:recommendations:{user_id}:{type}  # 타입별 추천
user:similar:{user_id}                 # 유사한 사용자 목록
```

#### 세션 캐시
```
session:chat:{session_id}              # 채팅 세션 정보
session:history:{session_id}           # 대화 히스토리
session:context:{session_id}           # 세션 컨텍스트
```

### 캐시 TTL 설정
```python
CACHE_TTL = {
    "user_profile": 3600,              # 1시간
    "user_vector": 7200,               # 2시간
    "recommendations": 1800,           # 30분
    "similar_users": 3600,             # 1시간
    "chat_session": 1800,              # 30분
    "chat_history": 3600,              # 1시간
}
```

---

## 데이터 관계도

### 핵심 엔티티 관계
```
UserProfile (1) ←→ (N) Bookmark
UserProfile (1) ←→ (N) UserActivity  
UserProfile (1) ←→ (N) ChatSession
UserProfile (1) ←→ (N) Recommendation

Bookmark (1) ←→ (N) BookmarkSimilarity
Bookmark (1) ←→ (N) UserActivity

ChatSession (1) ←→ (N) UserActivity
```

### 외래 키 제약 조건
```sql
-- 북마크 → 사용자 프로필
ALTER TABLE bookmarks 
ADD CONSTRAINT fk_bookmarks_user_id 
FOREIGN KEY (user_id) REFERENCES user_profiles(user_id);

-- 사용자 활동 → 사용자 프로필
ALTER TABLE user_activities 
ADD CONSTRAINT fk_activities_user_id 
FOREIGN KEY (user_id) REFERENCES user_profiles(user_id);

-- 북마크 유사도 → 북마크들
ALTER TABLE bookmark_similarities 
ADD CONSTRAINT fk_similarity_bookmark_id 
FOREIGN KEY (bookmark_id) REFERENCES bookmarks(bookmark_id);

ALTER TABLE bookmark_similarities 
ADD CONSTRAINT fk_similarity_similar_bookmark_id 
FOREIGN KEY (similar_bookmark_id) REFERENCES bookmarks(bookmark_id);
```

---

## 데이터 마이그레이션 및 버전 관리

### 스키마 버전 관리
```sql
CREATE TABLE schema_versions (
    version VARCHAR(20) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT,
    migration_sql TEXT
);
```

### 데이터 마이그레이션 예시
```python
# 프로필 벡터 차원 변경 마이그레이션
def migrate_vector_dimension():
    """벡터 차원을 512에서 768로 변경"""
    
    # 1. 새로운 컬럼 추가
    execute_sql("ALTER TABLE user_profiles ADD COLUMN profile_vector_new vector(768)")
    
    # 2. 기존 벡터를 새 차원으로 변환
    users = get_all_users()
    for user in users:
        old_vector = user.profile_vector  # 512차원
        new_vector = resize_vector(old_vector, 768)  # 768차원으로 확장
        update_user_vector(user.user_id, new_vector)
    
    # 3. 기존 컬럼 삭제 및 새 컬럼 이름 변경
    execute_sql("ALTER TABLE user_profiles DROP COLUMN profile_vector")
    execute_sql("ALTER TABLE user_profiles RENAME COLUMN profile_vector_new TO profile_vector")
```

---

## 성능 최적화

### 인덱스 전략
```sql
-- 복합 인덱스 (자주 함께 사용되는 컬럼들)
CREATE INDEX bookmarks_user_created_idx ON bookmarks(user_id, created_at DESC);
CREATE INDEX activities_user_type_time_idx ON user_activities(user_id, activity_type, timestamp DESC);

-- 부분 인덱스 (특정 조건의 데이터만)
CREATE INDEX bookmarks_processed_idx ON bookmarks(processing_status) 
WHERE processing_status = 'processed';

-- 표현식 인덱스 (계산된 값)
CREATE INDEX bookmarks_domain_lower_idx ON bookmarks(LOWER(domain));
```

### 파티셔닝 전략
```sql
-- 시간 기반 파티셔닝 (대용량 활동 데이터)
CREATE TABLE user_activities_2024_01 PARTITION OF user_activities
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE user_activities_2024_02 PARTITION OF user_activities
FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

---

이 데이터 모델 문서는 Nebula AI 시스템의 모든 데이터 구조를 포괄적으로 다루며, 시스템 확장과 함께 지속적으로 업데이트됩니다. 