# Nebula AI API 참조 문서

## 개요

Nebula AI API는 Spring Boot 서버와 AI 서버(FastAPI) 간의 통신을 위한 RESTful API입니다. CQRS 패턴을 기반으로 하여 읽기와 쓰기 작업을 효율적으로 분리했습니다.

## 기본 정보

- **기본 URL**: `http://localhost:8000`
- **API 버전**: `v1`
- **인증**: API 키 기반 (개발 중)
- **Content-Type**: `application/json`
- **문자 인코딩**: `UTF-8`

## API 엔드포인트 개요

### 핵심 서비스
1. **User Profile API** - 사용자 프로필 관리 (CQRS Query Side)
2. **Chat Stream API** - 실시간 채팅 및 RAG 검색
3. **Health Check API** - 서비스 상태 확인

---

## 1. User Profile API

### 1.1 사용자 프로필 조회

사용자의 프로필 정보를 조회합니다.

**엔드포인트**
```
GET /api/v1/profiles/{user_id}
```

**요청 매개변수**
| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `user_id` | integer | 필수 | 사용자 ID (경로 매개변수) |
| `include_metadata` | boolean | 선택 | 메타데이터 포함 여부 (기본값: false) |

**응답 스키마**
```json
{
  "user_id": 123,
  "profile_vector": [0.1, 0.2, ...],
  "last_updated": "2024-01-15T10:30:00Z",
  "vector_strength": 0.85,
  "completeness_score": 0.92,
  "created_at": "2024-01-01T00:00:00Z",
  "vector_metadata": {
    "source": "bookmark_analysis",
    "update_count": 15
  },
  "update_count": 15,
  "last_similarity_update": "2024-01-15T08:20:00Z"
}
```

**응답 코드**
- `200 OK`: 성공
- `404 Not Found`: 사용자 프로필을 찾을 수 없음
- `500 Internal Server Error`: 서버 오류

**사용 예시**
```bash
curl -X GET "http://localhost:8000/api/v1/profiles/123?include_metadata=true"
```

### 1.2 유사한 사용자 검색

현재 사용자와 유사한 관심사를 가진 사용자들을 검색합니다.

**엔드포인트**
```
GET /api/v1/profiles/{user_id}/similar
```

**요청 매개변수**
| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `user_id` | integer | 필수 | 기준 사용자 ID |
| `limit` | integer | 선택 | 반환할 사용자 수 (1-50, 기본값: 10) |
| `min_similarity` | float | 선택 | 최소 유사도 임계값 (0.0-1.0, 기본값: 0.5) |

**응답 스키마**
```json
{
  "user_id": 123,
  "similar_users": [
    {
      "user_id": 456,
      "similarity_score": 0.78,
      "shared_interests": ["AI", "Machine Learning", "Python"],
      "last_updated": "2024-01-15T10:30:00Z"
    }
  ],
  "total_found": 5,
  "search_criteria": {
    "min_similarity": 0.5,
    "limit": 10
  }
}
```

**사용 예시**
```bash
curl -X GET "http://localhost:8000/api/v1/profiles/123/similar?limit=20&min_similarity=0.7"
```

### 1.3 개인화 추천 조회

사용자별 맞춤 추천 콘텐츠를 조회합니다.

**엔드포인트**
```
GET /api/v1/profiles/{user_id}/recommendations
```

**요청 매개변수**
| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `user_id` | integer | 필수 | 사용자 ID |
| `category` | string | 선택 | 추천 카테고리 필터 |
| `max_age_hours` | integer | 선택 | 추천 최대 나이(시간) (1-168, 기본값: 24) |

**응답 스키마**
```json
{
  "user_id": 123,
  "recommendations": [
    {
      "id": "rec_001",
      "type": "content",
      "title": "머신러닝 트렌드 분석",
      "description": "2024년 최신 ML 동향",
      "score": 0.92,
      "metadata": {
        "source": "bookmark_analysis",
        "category": "technology"
      },
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "generated_at": "2024-01-15T10:00:00Z",
  "cache_status": "HIT",
  "refresh_requested": false
}
```

### 1.4 실시간 추천 생성

사용자를 위한 새로운 추천을 실시간으로 생성합니다.

**엔드포인트**
```
POST /api/v1/profiles/{user_id}/recommendations/generate
```

**요청 매개변수**
| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `user_id` | integer | 필수 | 사용자 ID |
| `limit` | integer | 선택 | 생성할 추천 수 (1-50, 기본값: 20) |
| `exclude_bookmarks` | boolean | 선택 | 기존 북마크 제외 여부 (기본값: true) |
| `diversity_boost` | boolean | 선택 | 다양성 증진 여부 (기본값: true) |

**응답 스키마**
```json
{
  "user_id": 123,
  "recommendations": [
    {
      "document_id": 1,
      "title": "AI 기초 가이드",
      "url": "https://example.com/ai-guide",
      "content": "인공지능의 기본 개념들",
      "keywords": ["AI", "인공지능", "머신러닝"],
      "summary": "AI에 대한 기초 설명",
      "recommendation_score": 0.85,
      "recommendation_type": "content_based",
      "reasoning": {
        "type": "content_based",
        "factors": [
          {
            "factor": "content_similarity",
            "description": "당신의 관심사와 유사한 콘텐츠",
            "weight": 0.8
          }
        ]
      }
    }
  ],
  "generated_at": "2024-01-15T10:30:00Z",
  "total_generated": 15,
  "tracking_ids": ["uuid1", "uuid2", "..."],
  "status": "success"
}
```

### 1.5 검색 기반 추천

검색어를 기반으로 개인화된 추천을 생성합니다.

**엔드포인트**
```
POST /api/v1/profiles/{user_id}/recommendations/search
```

**요청 매개변수**
| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `user_id` | integer | 필수 | 사용자 ID |
| `search_query` | string | 필수 | 검색어 |
| `limit` | integer | 선택 | 추천 결과 수 (1-30, 기본값: 15) |
| `personalization_weight` | float | 선택 | 개인화 가중치 (0.0-1.0, 기본값: 0.4) |

**응답 스키마**
```json
{
  "user_id": 123,
  "search_query": "machine learning",
  "recommendations": [
    {
      "document_id": 2,
      "title": "머신러닝 실전 가이드",
      "url": "https://example.com/ml-practical",
      "semantic_similarity": 0.9,
      "recommendation_score": 0.88,
      "personalization_score": 0.7,
      "keyword_match_score": 0.8,
      "reasoning": {
        "type": "search_based",
        "search_query": "machine learning",
        "expanded_keywords": ["machine", "learning", "ai", "머신러닝"],
        "factors": [
          {
            "factor": "semantic_similarity",
            "description": "'machine learning'와 의미적으로 유사한 콘텐츠",
            "weight": 0.9
          },
          {
            "factor": "keyword_matching",
            "description": "검색어와 관련된 키워드 포함",
            "weight": 0.8
          },
          {
            "factor": "personalization",
            "description": "당신의 관심사와 일치하는 콘텐츠",
            "weight": 0.7
          }
        ],
        "confidence": 0.88
      }
    }
  ],
  "generated_at": "2024-01-15T10:35:00Z",
  "total_found": 12,
  "tracking_ids": ["uuid3", "uuid4", "..."],
  "personalization_applied": 0.4,
  "status": "success"
}
```

### 1.6 추천 피드백 기록

추천에 대한 사용자 행동을 기록합니다.

**엔드포인트**
```
POST /api/v1/profiles/{user_id}/recommendations/{recommendation_id}/feedback
```

**요청 매개변수**
| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `user_id` | integer | 필수 | 사용자 ID |
| `recommendation_id` | string | 필수 | 추천 기록 UUID |
| `action` | string | 필수 | 사용자 액션 (clicked, saved, dismissed, ignored) |
| `additional_data` | object | 선택 | 추가 피드백 데이터 |

**요청 본문 예시**
```json
{
  "additional_data": {
    "session_duration": 120,
    "scroll_depth": 0.8,
    "time_spent": 45
  }
}
```

**응답 스키마**
```json
{
  "user_id": 123,
  "recommendation_id": "uuid1",
  "action": "clicked",
  "recorded_at": "2024-01-15T10:40:00Z",
  "status": "recorded"
}
```

### 1.7 관심사 분석

사용자의 관심사를 키워드와 토픽 수준에서 분석합니다.

**엔드포인트**
```
GET /api/v1/profiles/{user_id}/interests
```

**요청 매개변수**
| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `user_id` | integer | 필수 | 사용자 ID |
| `include_keywords` | boolean | 선택 | 키워드 분석 포함 (기본값: true) |
| `include_topics` | boolean | 선택 | 토픽 분석 포함 (기본값: true) |

**응답 스키마**
```json
{
  "user_id": 123,
  "keyword_analysis": {
    "top_keywords": [
      {"keyword": "AI", "weight": 0.95, "frequency": 45},
      {"keyword": "Python", "weight": 0.87, "frequency": 32}
    ],
    "trending_keywords": ["GPT-4", "LangChain"],
    "keyword_evolution": {
      "emerging": ["Vector DB", "RAG"],
      "declining": ["TensorFlow 1.x"]
    }
  },
  "topic_analysis": {
    "primary_topics": [
      {"topic": "Machine Learning", "confidence": 0.89},
      {"topic": "Software Development", "confidence": 0.76}
    ],
    "topic_distribution": {
      "technology": 0.65,
      "science": 0.25,
      "business": 0.10
    }
  },
  "analysis_metadata": {
    "last_updated": "2024-01-15T10:30:00Z",
    "data_points": 150,
    "confidence": 0.87
  }
}
```

### 1.8 프로필 메트릭 조회

사용자 프로필의 상세 메트릭 정보를 조회합니다.

**엔드포인트**
```
GET /api/v1/profiles/{user_id}/metrics
```

**응답 스키마**
```json
{
  "user_id": 123,
  "quality_metrics": {
    "completeness_score": 0.92,
    "vector_strength": 0.85,
    "activity_level": 0.78,
    "diversity_score": 0.91,
    "recency_score": 0.88,
    "overall_quality": 0.87
  },
  "activity_metrics": {
    "total_bookmarks": 245,
    "recent_activity": 15,
    "engagement_score": 0.76,
    "session_count": 89
  },
  "update_metrics": {
    "last_updated": "2024-01-15T10:30:00Z",
    "update_frequency": "daily",
    "next_scheduled_update": "2024-01-16T02:00:00Z",
    "update_count": 15
  }
}
```

### 1.9 작업 상태 조회

비동기 작업의 진행 상태를 조회합니다.

**엔드포인트**
```
GET /api/v1/profiles/jobs/{job_id}/status
```

**응답 스키마**
```json
{
  "job_id": "job_12345",
  "status": "PENDING",
  "progress": 45,
  "message": "프로필 벡터 업데이트 중...",
  "started_at": "2024-01-15T10:00:00Z",
  "estimated_completion": "2024-01-15T10:05:00Z",
  "result": null
}
```

**작업 상태**
- `PENDING`: 대기 중
- `RUNNING`: 실행 중
- `SUCCESS`: 완료
- `FAILED`: 실패
- `CANCELLED`: 취소됨

---

## 2. Chat Stream API

### 2.1 스트리밍 채팅

RAG 기반 스트리밍 채팅 응답을 제공합니다.

**엔드포인트**
```
POST /api/v1/chat/stream
```

**요청 스키마**
```json
{
  "user_id": 123,
  "message": "AI에 대해 설명해주세요",
  "session_id": "session_abc123",
  "context": {
    "include_history": true,
    "max_history": 10,
    "search_similar": true
  }
}
```

**응답** (Server-Sent Events)
```
data: {"type": "token", "content": "AI는", "timestamp": "2024-01-15T10:30:00Z"}

data: {"type": "token", "content": " 인공지능으로", "timestamp": "2024-01-15T10:30:01Z"}

data: {"type": "reference", "content": {"source": "bookmark_123", "title": "AI 기초"}}

data: {"type": "complete", "total_tokens": 150, "session_id": "session_abc123"}
```

**요청 매개변수**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `user_id` | integer | 필수 | 사용자 ID |
| `message` | string | 필수 | 사용자 메시지 |
| `session_id` | string | 선택 | 세션 ID (연속 대화용) |
| `context.include_history` | boolean | 선택 | 대화 히스토리 포함 |
| `context.max_history` | integer | 선택 | 최대 히스토리 수 |
| `context.search_similar` | boolean | 선택 | 유사 콘텐츠 검색 |

**스트리밍 이벤트 타입**
- `token`: 텍스트 토큰
- `reference`: 참조 정보
- `complete`: 응답 완료
- `error`: 오류 발생

---

## 3. Health Check API

### 3.1 서비스 상태 확인

**엔드포인트**
```
GET /health
```

**응답 스키마**
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "rabbitmq": "connected",
    "redis": "connected",
    "vector_db": "connected"
  },
  "version": "1.0.0",
  "uptime": "2 days, 3 hours",
  "last_check": "2024-01-15T10:30:00Z"
}
```

### 3.2 루트 엔드포인트

**엔드포인트**
```
GET /
```

**응답 스키마**
```json
{
  "message": "Nebula AI - User Profile API",
  "version": "1.0.0",
  "endpoints": {
    "profiles": "/api/v1/profiles",
    "docs": "/docs",
    "health": "/health"
  }
}
```

---

## 4. 에러 처리

### 4.1 표준 에러 응답

모든 API는 다음 형식의 에러 응답을 반환합니다:

```json
{
  "detail": "User profile not found",
  "error_code": "PROFILE_NOT_FOUND",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_12345"
}
```

### 4.2 에러 코드

| 코드 | HTTP 상태 | 설명 |
|------|-----------|------|
| `PROFILE_NOT_FOUND` | 404 | 사용자 프로필을 찾을 수 없음 |
| `INVALID_USER_ID` | 400 | 잘못된 사용자 ID |
| `VECTOR_NOT_READY` | 404 | 프로필 벡터가 아직 생성되지 않음 |
| `SIMILARITY_CALCULATION_FAILED` | 500 | 유사도 계산 실패 |
| `RECOMMENDATION_SERVICE_ERROR` | 503 | 추천 서비스 오류 |
| `DATABASE_CONNECTION_ERROR` | 503 | 데이터베이스 연결 오류 |

---

## 5. 인증 및 보안

### 5.1 API 키 인증 (개발 중)

```bash
curl -X GET "http://localhost:8000/api/v1/profiles/123" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 5.2 Rate Limiting

- **기본 제한**: 100 요청/분
- **버스트 제한**: 10 요청/초
- **헤더**: `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### 5.3 CORS 설정

- **허용 Origin**: 개발 시 `*`, 프로덕션에서는 특정 도메인으로 제한
- **허용 메소드**: `GET`, `POST`, `PUT`, `DELETE`
- **허용 헤더**: `Content-Type`, `Authorization`

---

## 6. 통합 가이드

### 6.1 Spring Boot 서버 통합 예시

```java
@Service
public class ProfileService {
    
    @Value("${ai.server.base-url}")
    private String aiServerUrl;
    
    private final RestTemplate restTemplate;
    
    public UserProfile getUserProfile(Long userId) {
        String url = aiServerUrl + "/api/v1/profiles/" + userId;
        
        try {
            ResponseEntity<UserProfileResponse> response = 
                restTemplate.getForEntity(url, UserProfileResponse.class);
            
            return response.getBody();
        } catch (HttpClientErrorException.NotFound e) {
            throw new UserProfileNotFoundException(userId);
        }
    }
    
    public List<SimilarUser> getSimilarUsers(Long userId, int limit) {
        String url = aiServerUrl + "/api/v1/profiles/" + userId + "/similar";
        
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(url)
            .queryParam("limit", limit)
            .queryParam("min_similarity", 0.7);
            
        ResponseEntity<SimilarUsersResponse> response = 
            restTemplate.getForEntity(builder.toUriString(), SimilarUsersResponse.class);
            
        return response.getBody().getSimilarUsers();
    }
}
```

### 6.2 프론트엔드 통합 예시

```javascript
// 사용자 프로필 조회
async function getUserProfile(userId) {
  const response = await fetch(`/api/v1/profiles/${userId}?include_metadata=true`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch profile: ${response.status}`);
  }
  
  return response.json();
}

// 스트리밍 채팅
async function startChatStream(userId, message) {
  const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_id: userId,
      message: message,
      context: {
        include_history: true,
        search_similar: true
      }
    })
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        handleStreamEvent(data);
      }
    }
  }
}

function handleStreamEvent(event) {
  switch (event.type) {
    case 'token':
      appendToken(event.content);
      break;
    case 'reference':
      addReference(event.content);
      break;
    case 'complete':
      finalizeResponse(event);
      break;
  }
}
```

---

## 7. 개발 및 테스트

### 7.1 OpenAPI/Swagger 문서

- **URL**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### 7.2 테스트 환경

```bash
# API 테스트 실행
pytest tests/integration/test_api.py -v

# 특정 엔드포인트 테스트
pytest tests/integration/test_profile_api.py::test_get_user_profile -v

# 성능 테스트
pytest tests/performance/test_api_performance.py -v
```

### 7.3 모니터링

- **Health Check**: `/health` 엔드포인트를 통한 서비스 상태 확인
- **메트릭**: Prometheus 메트릭 수집 (개발 중)
- **로그**: 구조화된 JSON 로그 형식

---

이 API 문서는 Nebula AI 시스템의 모든 외부 인터페이스를 다루며, 지속적으로 업데이트됩니다. 추가 질문이나 지원이 필요한 경우 개발팀에 문의해주세요. 