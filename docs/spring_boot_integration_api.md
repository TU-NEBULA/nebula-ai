# 🔗 스프링부트 - Nebula AI 연동 API 가이드

본 문서는 스프링부트 애플리케이션과 Nebula AI 시스템 간의 연동에 필요한 데이터 형식과 API 엔드포인트를 정의합니다.

## 📋 목차
- [RabbitMQ 메시지 형식](#rabbitmq-메시지-형식)
- [REST API 엔드포인트](#rest-api-엔드포인트)
- [공통 데이터 형식](#공통-데이터-형식)
- [에러 처리](#에러-처리)
- [Java 구현 예시](#java-구현-예시)

---

## 🐰 RabbitMQ 메시지 형식

> **💡 중요**: Nebula AI는 사용자 행동에 따라 **프로필을 자동으로 업데이트**합니다.  
> 스프링부트에서는 **데이터 제공**만 하면 되고, 프로필 업데이트나 추천 갱신은 자동 처리됩니다.

### 1. 북마크 저장 (`bookmark_save` 큐) ⭐

**사용 시점**: 사용자가 웹 콘텐츠를 북마크할 때

```json
{
  "userId": 123,
  "starId": "star_456",
  "s3Key": "users/123/bookmarks/document.pdf", 
  "title": "AI 기술 동향 보고서",
  "url": "https://example.com/ai-report",
  "keywords": ["AI", "머신러닝", "딥러닝"],
  "memo": "중요한 AI 기술 동향 정리",
  "summary": "2024년 AI 기술의 주요 발전 사항을 다룬 보고서"
}
```

**필수 필드**:
- `userId` (int): 사용자 ID (양수)
- `starId` (string): 북마크 고유 ID
- `s3Key` (string): S3 파일 경로
- `title` (string): 북마크 제목
- `url` (string): 원본 URL

**선택 필드**:
- `keywords` (array): 키워드 목록
- `memo` (string): 사용자 메모
- `summary` (string): 요약

**자동 처리사항**:
- ✅ HTML 콘텐츠 다운로드 및 텍스트 추출
- ✅ 기존 북마크와의 유사도 계산
- ✅ 벡터 DB에 자동 저장
- ✅ **사용자 프로필 자동 업데이트**
- ✅ 관계 데이터 자동 생성

### 2. 데이터 추출 요청 (`extract_request` 큐) ⭐

**사용 시점**: 새로운 웹 콘텐츠의 키워드/이미지 추출이 필요할 때

```json
{
  "user_id": 123,
  "url": "https://example.com/article",
  "s3_key": "temp/extracts/content_789.html"
}
```

**필수 필드**:
- `user_id` (int): 사용자 ID
- `url` (string): 원본 URL  
- `s3_key` (string): S3에 저장된 HTML 파일 경로

**자동 처리사항**:
- ✅ HTML에서 이미지 URL 추출
- ✅ 키워드 자동 추출
- ✅ NLP 처리 및 메타데이터 생성

---

## 🌐 REST API 엔드포인트

### 1. 사용자 프로필 조회

```http
GET /api/v1/profiles/{user_id}?include_metadata=true
```

**응답 형식**:
```json
{
  "user_id": 123,
  "profile_vector": [0.1, 0.5, -0.3, ...],
  "last_updated": "2024-01-15T10:30:00Z",
  "vector_strength": 0.85,
  "completeness_score": 78,
  "created_at": "2024-01-01T00:00:00Z",
  "vector_metadata": {
    "algorithm_version": "v2.1",
    "data_sources": ["bookmarks", "chats"],
    "last_similarity_update": "2024-01-15T09:00:00Z"
  }
}
```

### 2. 유사 사용자 검색

```http
GET /api/v1/profiles/{user_id}/similar?limit=10&min_similarity=0.7
```

**응답 형식**:
```json
{
  "user_id": 123,
  "similar_users": [
    {
      "user_id": 456,
      "similarity_score": 0.89,
      "shared_interests": ["AI", "머신러닝"],
      "last_updated": "2024-01-15T10:00:00Z"
    }
  ],
  "total_found": 5,
  "search_criteria": {
    "min_similarity": 0.7,
    "limit": 10
  }
}
```

### 3. 개인화 추천 조회

```http
GET /api/v1/profiles/{user_id}/recommendations?category=tech&max_age_hours=24
```

**응답 형식**:
```json
{
  "user_id": 123,
  "recommendations": [
    {
      "id": 789,
      "type": "article",
      "title": "최신 AI 동향",
      "description": "2024년 AI 기술 발전 현황",
      "score": 0.92,
      "metadata": {
        "category": "tech",
        "source": "tech_blog"
      },
      "created_at": "2024-01-15T08:00:00Z"
    }
  ],
  "generated_at": "2024-01-15T08:00:00Z",
  "cache_status": "HIT",
  "refresh_requested": false
}
```

### 4. 채팅 스트림

```http
POST /chat/stream
Content-Type: application/json

{
  "user_id": 123,
  "message": "AI 기술에 대해 알려줘",
  "session_id": "session_456"
}
```

**SSE 스트림 응답**:
```
data: {"type": "session_start", "data": {"session_id": "session_456", "user_message_id": "msg_789"}}

data: {"type": "chunk", "data": "AI 기술은"}

data: {"type": "chunk", "data": " 인공지능을"}

data: {"type": "end", "data": {"session_id": "session_456", "total_tokens": 150}}
```

### 5. 채팅 세션 관리

**새 세션 생성**:
```http
POST /chat/sessions
{
  "user_id": 123,
  "title": "AI 기술 상담"
}
```

**세션 목록 조회**:
```http
GET /chat/sessions?user_id=123&limit=20&offset=0
```

### 6. 작업 상태 조회

```http
GET /api/v1/profiles/jobs/{job_id}/status
```

**응답 형식**:
```json
{
  "job_id": "job_abc123",
  "status": "IN_PROGRESS",
  "progress_percentage": 45,
  "started_at": "2024-01-15T10:00:00Z",
  "estimated_completion": "2024-01-15T10:15:00Z",
  "result_data": null,
  "error_message": null
}
```

---

## 📊 공통 데이터 형식

### 상태 코드
- `PENDING`: 대기 중
- `IN_PROGRESS`: 진행 중  
- `COMPLETED`: 완료
- `FAILED`: 실패
- `CANCELLED`: 취소됨

### 캐시 상태
- `HIT`: 캐시에서 조회
- `MISS`: 캐시 미스
- `EXPIRED`: 캐시 만료

### 작업 우선순위
- `high`: 높음 (즉시 처리)
- `normal`: 보통 (순차 처리)
- `low`: 낮음 (백그라운드 처리)

---

## ⚠️ 에러 처리

### 공통 에러 응답 형식

```json
{
  "success": false,
  "message": "사용자를 찾을 수 없습니다",
  "error_code": "USER_NOT_FOUND",
  "details": {
    "user_id": 123,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### 주요 에러 코드

| 코드 | 설명 | HTTP 상태 |
|------|------|-----------|
| `USER_NOT_FOUND` | 사용자 없음 | 404 |
| `PROFILE_NOT_READY` | 프로필 준비되지 않음 | 202 |
| `INVALID_REQUEST` | 잘못된 요청 | 400 |
| `RATE_LIMIT_EXCEEDED` | 요청 한도 초과 | 429 |
| `INTERNAL_ERROR` | 서버 내부 오류 | 500 |

---

## ☕ Java 구현 예시

### 1. RabbitMQ 메시지 발송 (핵심)

```java
@Service
public class NebulaAIMessageService {
    
    private final RabbitTemplate rabbitTemplate;
    
    // 🎯 핵심: 북마크 저장 시 호출
    public void sendBookmarkSave(BookmarkSaveRequest request) {
        try {
            rabbitTemplate.convertAndSend("bookmark_save", request);
            log.info("북마크 저장 메시지 발송: userId={}, starId={}", 
                request.getUserId(), request.getStarId());
        } catch (Exception e) {
            log.error("북마크 저장 메시지 발송 실패", e);
            throw new MessageSendException("북마크 저장 요청 실패", e);
        }
    }
    
    // 🎯 핵심: 데이터 추출 요청 시 호출
    public void sendExtractRequest(ExtractDataRequest request) {
        try {
            rabbitTemplate.convertAndSend("extract_request", request);
            log.info("데이터 추출 메시지 발송: userId={}, url={}", 
                request.getUserId(), request.getUrl());
        } catch (Exception e) {
            log.error("데이터 추출 메시지 발송 실패", e);
            throw new MessageSendException("데이터 추출 요청 실패", e);
        }
    }
}
```

### 2. REST API 클라이언트

```java
@Component
public class NebulaAIClient {
    
    private final RestTemplate restTemplate;
    private final String baseUrl;
    
    public UserProfileResponse getUserProfile(Long userId, boolean includeMetadata) {
        String url = String.format("%s/api/v1/profiles/%d?include_metadata=%s", 
            baseUrl, userId, includeMetadata);
            
        try {
            return restTemplate.getForObject(url, UserProfileResponse.class);
        } catch (HttpClientErrorException.NotFound e) {
            throw new UserNotFoundException("사용자 프로필을 찾을 수 없습니다: " + userId);
        } catch (Exception e) {
            log.error("프로필 조회 실패: userId={}", userId, e);
            throw new NebulaAIException("프로필 조회 실패", e);
        }
    }
    
    public SimilarUsersResponse getSimilarUsers(Long userId, int limit, double minSimilarity) {
        String url = String.format("%s/api/v1/profiles/%d/similar?limit=%d&min_similarity=%.2f",
            baseUrl, userId, limit, minSimilarity);
            
        return restTemplate.getForObject(url, SimilarUsersResponse.class);
    }
    
    public RecommendationsResponse getRecommendations(Long userId, String category) {
        String url = String.format("%s/api/v1/profiles/%d/recommendations?category=%s",
            baseUrl, userId, category != null ? category : "");
            
        return restTemplate.getForObject(url, RecommendationsResponse.class);
    }
}
```

### 3. 이벤트 기반 연동 (간소화)

```java
@Component
public class BookmarkEventListener {
    
    private final NebulaAIMessageService messageService;
    
    @EventListener
    public void handleBookmarkSaved(BookmarkSavedEvent event) {
        BookmarkSaveRequest request = BookmarkSaveRequest.builder()
            .userId(event.getUserId())
            .starId(event.getStarId())
            .s3Key(event.getS3Key())
            .title(event.getTitle())
            .url(event.getUrl())
            .keywords(event.getKeywords())
            .memo(event.getMemo())
            .summary(event.getSummary())
            .build();
            
        // 🎯 핵심: 북마크 저장하면 Nebula AI가 모든 것을 자동 처리
        messageService.sendBookmarkSave(request);
    }
    
    @EventListener 
    public void handleContentExtractionNeeded(ContentExtractionEvent event) {
        ExtractDataRequest request = ExtractDataRequest.builder()
            .userId(event.getUserId())
            .url(event.getUrl())
            .s3Key(event.getS3Key())
            .build();
            
        // 🎯 핵심: 콘텐츠 분석 요청
        messageService.sendExtractRequest(request);
    }
}
```

---

## 📝 실제 연동 체크리스트

### ✅ 필수 구현 항목 (간소화)

- [ ] RabbitMQ 연결 설정
- [ ] **북마크 저장 메시지 발송** (가장 중요)
- [ ] **데이터 추출 메시지 발송** (선택적)
- [ ] REST API 클라이언트 구현 (프로필 조회, 추천 조회)
- [ ] 에러 처리 및 재시도 로직
- [ ] 이벤트 기반 연동 구현

### 🔧 환경 설정

```properties
# application.properties
spring.rabbitmq.host=${RABBITMQ_HOST:localhost}
spring.rabbitmq.port=${RABBITMQ_PORT:5672}
spring.rabbitmq.username=${RABBITMQ_USERNAME:guest}
spring.rabbitmq.password=${RABBITMQ_PASSWORD:guest}

nebula.ai.base-url=${NEBULA_AI_BASE_URL:http://localhost:8000}
nebula.ai.timeout=${NEBULA_AI_TIMEOUT:30}

# 필요한 큐만 설정
nebula.ai.queues.bookmark-save=bookmark_save
nebula.ai.queues.extract-request=extract_request
```

---

## 🚀 **핵심 포인트**

1. **스프링부트는 데이터만 제공** - Nebula AI가 모든 분석과 프로필 업데이트를 자동 처리
2. **필수 연동**: 북마크 저장 메시지 발송
3. **선택 연동**: 데이터 추출 요청 (새 콘텐츠 분석 시)
4. **자동 처리**: 프로필 업데이트, 유사도 계산, 추천 갱신 등
5. **조회 API**: 완성된 프로필과 추천 데이터 조회

**참고**: 실제 운영 환경에서는 보안, 모니터링, 로깅 등을 추가로 고려해야 합니다. 