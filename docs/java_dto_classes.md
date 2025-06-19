# 📦 Java DTO 클래스 정의

Nebula AI 연동을 위한 Java DTO(Data Transfer Object) 클래스들입니다.

> **💡 중요**: Nebula AI는 프로필을 자동으로 관리하므로, 스프링부트에서는 **데이터 제공용 DTO**만 필요합니다.

## 📋 목차
- [RabbitMQ 메시지 DTO](#rabbitmq-메시지-dto)
- [API 응답 DTO](#api-응답-dto)
- [채팅 관련 DTO](#채팅-관련-dto)
- [공통 DTO](#공통-dto)

---

## 🐰 RabbitMQ 메시지 DTO

### BookmarkSaveRequest.java ⭐
```java
package com.example.dto.message;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Positive;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BookmarkSaveRequest {
    
    @NotNull
    @Positive
    @JsonProperty("userId")
    private Long userId;
    
    @NotBlank
    @JsonProperty("starId")
    private String starId;
    
    @NotBlank
    @JsonProperty("s3Key")
    private String s3Key;
    
    @NotBlank
    @JsonProperty("title")
    private String title;
    
    @NotBlank
    @JsonProperty("url")
    private String url;
    
    @JsonProperty("keywords")
    private List<String> keywords;
    
    @JsonProperty("memo")
    private String memo;
    
    @JsonProperty("summary")
    private String summary;
}
```

### ExtractDataRequest.java ⭐
```java
package com.example.dto.message;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Positive;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ExtractDataRequest {
    
    @NotNull
    @Positive
    @JsonProperty("user_id")
    private Long userId;
    
    @NotBlank
    @JsonProperty("url")
    private String url;
    
    @NotBlank
    @JsonProperty("s3_key")
    private String s3Key;
}
```

---

## 🌐 API 응답 DTO

### UserProfileResponse.java
```java
package com.example.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
public class UserProfileResponse {
    
    @JsonProperty("user_id")
    private Long userId;
    
    @JsonProperty("profile_vector")
    private List<Double> profileVector;
    
    @JsonProperty("last_updated")
    private LocalDateTime lastUpdated;
    
    @JsonProperty("vector_strength")
    private Double vectorStrength;
    
    @JsonProperty("completeness_score")
    private Integer completenessScore;
    
    // 메타데이터 (선택적)
    @JsonProperty("created_at")
    private LocalDateTime createdAt;
    
    @JsonProperty("vector_metadata")
    private Map<String, Object> vectorMetadata;
    
    @JsonProperty("update_count")
    private Integer updateCount;
    
    @JsonProperty("last_similarity_update")
    private LocalDateTime lastSimilarityUpdate;
}
```

### SimilarUsersResponse.java
```java
package com.example.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

@Data
public class SimilarUsersResponse {
    
    @JsonProperty("user_id")
    private Long userId;
    
    @JsonProperty("similar_users")
    private List<SimilarUserItem> similarUsers;
    
    @JsonProperty("total_found")
    private Integer totalFound;
    
    @JsonProperty("search_criteria")
    private SearchCriteria searchCriteria;
    
    @Data
    public static class SimilarUserItem {
        @JsonProperty("user_id")
        private Long userId;
        
        @JsonProperty("similarity_score")
        private Double similarityScore;
        
        @JsonProperty("shared_interests")
        private List<String> sharedInterests;
        
        @JsonProperty("last_updated")
        private LocalDateTime lastUpdated;
    }
    
    @Data
    public static class SearchCriteria {
        @JsonProperty("min_similarity")
        private Double minSimilarity;
        
        @JsonProperty("limit")
        private Integer limit;
    }
}
```

### RecommendationsResponse.java
```java
package com.example.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
public class RecommendationsResponse {
    
    @JsonProperty("user_id")
    private Long userId;
    
    @JsonProperty("recommendations")
    private List<RecommendationItem> recommendations;
    
    @JsonProperty("generated_at")
    private LocalDateTime generatedAt;
    
    @JsonProperty("cache_status")
    private String cacheStatus; // HIT, MISS, EXPIRED
    
    @JsonProperty("refresh_requested")
    private Boolean refreshRequested;
    
    @Data
    public static class RecommendationItem {
        @JsonProperty("id")
        private Long id;
        
        @JsonProperty("type")
        private String type;
        
        @JsonProperty("title")
        private String title;
        
        @JsonProperty("description")
        private String description;
        
        @JsonProperty("score")
        private Double score;
        
        @JsonProperty("metadata")
        private Map<String, Object> metadata;
        
        @JsonProperty("created_at")
        private LocalDateTime createdAt;
    }
}
```

### JobStatusResponse.java
```java
package com.example.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

@Data
public class JobStatusResponse {
    
    @JsonProperty("job_id")
    private String jobId;
    
    @JsonProperty("status")
    private JobStatus status;
    
    @JsonProperty("progress_percentage")
    private Integer progressPercentage;
    
    @JsonProperty("started_at")
    private LocalDateTime startedAt;
    
    @JsonProperty("estimated_completion")
    private LocalDateTime estimatedCompletion;
    
    @JsonProperty("result_data")
    private Map<String, Object> resultData;
    
    @JsonProperty("error_message")
    private String errorMessage;
    
    public enum JobStatus {
        PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    }
}
```

---

## 💬 채팅 관련 DTO

### ChatRequest.java
```java
package com.example.dto.chat;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Positive;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatRequest {
    
    @NotNull
    @Positive
    @JsonProperty("user_id")
    private Long userId;
    
    @NotBlank
    @JsonProperty("message")
    private String message;
    
    @JsonProperty("session_id")
    private String sessionId;
}
```

### ChatSessionCreateRequest.java
```java
package com.example.dto.chat;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.validation.constraints.NotNull;
import javax.validation.constraints.Positive;
import javax.validation.constraints.Size;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatSessionCreateRequest {
    
    @NotNull
    @Positive
    @JsonProperty("user_id")
    private Long userId;
    
    @Size(max = 500)
    @JsonProperty("title")
    private String title;
    
    @Size(max = 50)
    @JsonProperty("session_type")
    @Builder.Default
    private String sessionType = "general";
}
```

### ChatSessionResponse.java
```java
package com.example.dto.chat;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ChatSessionResponse {
    
    @JsonProperty("id")
    private String id;
    
    @JsonProperty("title")
    private String title;
    
    @JsonProperty("session_type")
    private String sessionType;
    
    @JsonProperty("created_at")
    private LocalDateTime createdAt;
    
    @JsonProperty("updated_at")
    private LocalDateTime updatedAt;
    
    @JsonProperty("is_active")
    private Boolean isActive;
}
```

### ChatMessageResponse.java
```java
package com.example.dto.chat;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

@Data
public class ChatMessageResponse {
    
    @JsonProperty("id")
    private String id;
    
    @JsonProperty("content")
    private String content;
    
    @JsonProperty("role")
    private String role; // user, assistant
    
    @JsonProperty("created_at")
    private LocalDateTime createdAt;
    
    @JsonProperty("metadata")
    private Map<String, Object> metadata;
}
```

---

## 📊 공통 DTO

### BaseResponse.java
```java
package com.example.dto.common;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BaseResponse<T> {
    
    @JsonProperty("success")
    @Builder.Default
    private Boolean success = true;
    
    @JsonProperty("message")
    @Builder.Default
    private String message = "Success";
    
    @JsonProperty("data")
    private T data;
    
    @JsonProperty("timestamp")
    @Builder.Default
    private LocalDateTime timestamp = LocalDateTime.now();
}
```

### ErrorResponse.java
```java
package com.example.dto.common;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ErrorResponse {
    
    @JsonProperty("success")
    @Builder.Default
    private Boolean success = false;
    
    @JsonProperty("message")
    private String message;
    
    @JsonProperty("error_code")
    private String errorCode;
    
    @JsonProperty("details")
    private Map<String, Object> details;
    
    @JsonProperty("timestamp")
    @Builder.Default
    private LocalDateTime timestamp = LocalDateTime.now();
}
```

### PaginationRequest.java
```java
package com.example.dto.common;

import lombok.Data;

import javax.validation.constraints.Max;
import javax.validation.constraints.Min;

@Data
public class PaginationRequest {
    
    @Min(1)
    private Integer page = 1;
    
    @Min(1)
    @Max(100)
    private Integer size = 20;
    
    private Integer offset = 0;
}
```

### PaginatedResponse.java
```java
package com.example.dto.common;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PaginatedResponse<T> {
    
    @JsonProperty("success")
    @Builder.Default
    private Boolean success = true;
    
    @JsonProperty("message")
    @Builder.Default
    private String message = "Success";
    
    @JsonProperty("data")
    private List<T> data;
    
    @JsonProperty("meta")
    private PaginationMeta meta;
    
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PaginationMeta {
        @JsonProperty("page")
        private Integer page;
        
        @JsonProperty("size")
        private Integer size;
        
        @JsonProperty("total")
        private Long total;
        
        @JsonProperty("total_pages")
        private Integer totalPages;
    }
}
```

---

## 🔧 Maven Dependencies

pom.xml에 추가할 의존성:

```xml
<dependencies>
    <!-- Spring Boot Starter Web -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    
    <!-- Spring Boot Starter AMQP (RabbitMQ) -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-amqp</artifactId>
    </dependency>
    
    <!-- Jackson (JSON 처리) -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
    </dependency>
    
    <!-- Lombok -->
    <dependency>
        <groupId>org.projectlombok</groupId>
        <artifactId>lombok</artifactId>
        <optional>true</optional>
    </dependency>
    
    <!-- Validation -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
</dependencies>
```

---

## 📝 사용 예시

### 메시지 발송 예시 (핵심)
```java
@Service
public class NebulaAIService {
    
    private final RabbitTemplate rabbitTemplate;
    
    // 🎯 가장 중요: 북마크 저장 시 자동으로 모든 처리됨
    public void sendBookmarkSaveMessage(Long userId, String starId, String s3Key, 
                                       String title, String url) {
        BookmarkSaveRequest request = BookmarkSaveRequest.builder()
            .userId(userId)
            .starId(starId)
            .s3Key(s3Key)
            .title(title)
            .url(url)
            .build();
            
        rabbitTemplate.convertAndSend("bookmark_save", request);
        // 🚀 이제 Nebula AI가 모든 분석과 프로필 업데이트를 자동 처리!
    }
    
    // 📊 선택적: 콘텐츠 분석 요청 시
    public void sendExtractDataMessage(Long userId, String url, String s3Key) {
        ExtractDataRequest request = ExtractDataRequest.builder()
            .userId(userId)
            .url(url)
            .s3Key(s3Key)
            .build();
            
        rabbitTemplate.convertAndSend("extract_request", request);
    }
}
```

### API 호출 예시
```java
@Service
public class ProfileService {
    
    private final NebulaAIClient nebulaAIClient;
    
    public UserProfileResponse getUserProfile(Long userId) {
        return nebulaAIClient.getUserProfile(userId, true);
    }
    
    public List<SimilarUserItem> getSimilarUsers(Long userId, int limit) {
        SimilarUsersResponse response = nebulaAIClient.getSimilarUsers(userId, limit, 0.7);
        return response.getSimilarUsers();
    }
    
    public List<RecommendationItem> getRecommendations(Long userId, String category) {
        RecommendationsResponse response = nebulaAIClient.getRecommendations(userId, category);
        return response.getRecommendations();
    }
}
```

## 🚀 **핵심 포인트**

1. **최소한의 DTO**: 데이터 제공용 (`BookmarkSaveRequest`, `ExtractDataRequest`)과 조회용 DTO만 필요
2. **자동 처리**: 프로필 관련 모든 업데이트는 Nebula AI가 자동 처리
3. **간단한 연동**: 북마크 저장 → 모든 분석 자동 완료
4. **조회 중심**: 완성된 프로필과 추천 데이터를 조회하는 용도

이 DTO 클래스들을 사용하여 Nebula AI와 효율적이고 간단한 연동을 구현할 수 있습니다! 🚀 