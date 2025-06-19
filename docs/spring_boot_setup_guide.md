# ⚙️ 스프링부트 - Nebula AI 연동 설정 가이드

본 문서는 스프링부트 애플리케이션에서 Nebula AI 시스템과 연동하기 위한 설정 방법을 제공합니다.

> **💡 핵심**: Nebula AI는 북마크 저장 시 자동으로 모든 분석과 프로필 업데이트를 처리합니다.  
> 스프링부트는 **데이터만 제공**하면 됩니다!

## 📋 목차
- [의존성 설정](#의존성-설정)
- [환경 설정](#환경-설정)
- [RabbitMQ 설정](#rabbitmq-설정)
- [REST Client 설정](#rest-client-설정)
- [이벤트 리스너 설정](#이벤트-리스너-설정)
- [예외 처리](#예외-처리)
- [테스트 설정](#테스트-설정)

---

## 📦 의존성 설정

### pom.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
        <relativePath/>
    </parent>
    
    <dependencies>
        <!-- Spring Boot Core -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <!-- RabbitMQ (핵심) -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-amqp</artifactId>
        </dependency>
        
        <!-- Validation -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        
        <!-- JSON 처리 -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>
        
        <dependency>
            <groupId>com.fasterxml.jackson.datatype</groupId>
            <artifactId>jackson-datatype-jsr310</artifactId>
        </dependency>
        
        <!-- Lombok -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        
        <!-- 모니터링 (선택사항) -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        
        <!-- 테스트 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

---

## 🔧 환경 설정

### application.yml
```yaml
spring:
  application:
    name: spring-boot-nebula-ai
  
  # RabbitMQ 설정 (핵심)
  rabbitmq:
    host: ${RABBITMQ_HOST:localhost}
    port: ${RABBITMQ_PORT:5672}
    username: ${RABBITMQ_USERNAME:guest}
    password: ${RABBITMQ_PASSWORD:guest}
    virtual-host: ${RABBITMQ_VHOST:/}
    connection-timeout: 30000
    listener:
      simple:
        retry:
          enabled: true
          initial-interval: 1000
          max-attempts: 3

  # Jackson 설정
  jackson:
    serialization:
      write-dates-as-timestamps: false
    deserialization:
      fail-on-unknown-properties: false

# Nebula AI 연동 설정
nebula:
  ai:
    base-url: ${NEBULA_AI_BASE_URL:http://localhost:8000}
    timeout: ${NEBULA_AI_TIMEOUT:30}
    retry:
      max-attempts: 3
      delay: 1000
    
    # 필요한 큐만 설정 (간소화)
    queues:
      bookmark-save: ${BOOKMARK_SAVE_QUEUE:bookmark_save}
      extract-request: ${EXTRACT_REQUEST_QUEUE:extract_request}

# 로깅 설정
logging:
  level:
    com.example.nebula: DEBUG
    org.springframework.amqp: INFO
    root: INFO
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"

# 모니터링 설정
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,rabbitmq
  endpoint:
    health:
      show-details: always
```

### application-dev.yml (개발 환경)
```yaml
spring:
  rabbitmq:
    host: localhost
    port: 5672

nebula:
  ai:
    base-url: http://localhost:8000

logging:
  level:
    com.example.nebula: DEBUG
    org.springframework.amqp: DEBUG
```

### application-prod.yml (운영 환경)
```yaml
spring:
  rabbitmq:
    host: ${RABBITMQ_HOST}
    port: ${RABBITMQ_PORT}
    username: ${RABBITMQ_USERNAME}
    password: ${RABBITMQ_PASSWORD}

nebula:
  ai:
    base-url: ${NEBULA_AI_BASE_URL}

logging:
  level:
    com.example.nebula: INFO
    org.springframework.amqp: WARN
```

---

## 🐰 RabbitMQ 설정 (간소화)

### RabbitMQConfig.java
```java
package com.example.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {
    
    @Value("${nebula.ai.queues.bookmark-save}")
    private String bookmarkSaveQueue;
    
    @Value("${nebula.ai.queues.extract-request}")
    private String extractRequestQueue;
    
    // 메시지 컨버터
    @Bean
    public Jackson2JsonMessageConverter messageConverter() {
        return new Jackson2JsonMessageConverter();
    }
    
    // RabbitTemplate 설정
    @Bean
    public RabbitTemplate rabbitTemplate(ConnectionFactory connectionFactory) {
        RabbitTemplate template = new RabbitTemplate(connectionFactory);
        template.setMessageConverter(messageConverter());
        template.setMandatory(true); // 메시지 전송 실패 시 예외 발생
        return template;
    }
    
    // 리스너 컨테이너 팩토리
    @Bean
    public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(
            ConnectionFactory connectionFactory) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        factory.setMessageConverter(messageConverter());
        factory.setDefaultRequeueRejected(false); // 실패한 메시지 재큐잉 방지
        return factory;
    }
    
    // 필요한 큐만 선언 (간소화)
    @Bean
    public Queue bookmarkSaveQueue() {
        return QueueBuilder.durable(bookmarkSaveQueue).build();
    }
    
    @Bean
    public Queue extractRequestQueue() {
        return QueueBuilder.durable(extractRequestQueue).build();
    }
}
```

### MessagePublisher.java (간소화)
```java
package com.example.service;

import com.example.dto.message.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class NebulaAIMessagePublisher {
    
    private final RabbitTemplate rabbitTemplate;
    
    @Value("${nebula.ai.queues.bookmark-save}")
    private String bookmarkSaveQueue;
    
    @Value("${nebula.ai.queues.extract-request}")
    private String extractRequestQueue;
    
    // 🎯 핵심: 북마크 저장 (가장 중요)
    public void publishBookmarkSave(BookmarkSaveRequest request) {
        try {
            rabbitTemplate.convertAndSend(bookmarkSaveQueue, request);
            log.info("📚 북마크 저장 메시지 발송 완료: userId={}, starId={}", 
                request.getUserId(), request.getStarId());
        } catch (Exception e) {
            log.error("❌ 북마크 저장 메시지 발송 실패: userId={}, starId={}", 
                request.getUserId(), request.getStarId(), e);
            throw new MessagePublishException("북마크 저장 메시지 발송 실패", e);
        }
    }
    
    // 📊 선택적: 데이터 추출 요청
    public void publishExtractRequest(ExtractDataRequest request) {
        try {
            rabbitTemplate.convertAndSend(extractRequestQueue, request);
            log.info("🔍 데이터 추출 메시지 발송 완료: userId={}, url={}", 
                request.getUserId(), request.getUrl());
        } catch (Exception e) {
            log.error("❌ 데이터 추출 메시지 발송 실패: userId={}, url={}", 
                request.getUserId(), request.getUrl(), e);
            throw new MessagePublishException("데이터 추출 메시지 발송 실패", e);
        }
    }
}
```

---

## 🌐 REST Client 설정

### RestTemplateConfig.java
```java
package com.example.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;

@Slf4j
@Configuration
public class RestTemplateConfig {
    
    @Value("${nebula.ai.timeout:30}")
    private int timeoutSeconds;
    
    @Bean
    public RestTemplate nebulaAIRestTemplate(RestTemplateBuilder builder) {
        return builder
            .setConnectTimeout(Duration.ofSeconds(timeoutSeconds))
            .setReadTimeout(Duration.ofSeconds(timeoutSeconds))
            .additionalInterceptors(loggingInterceptor())
            .build();
    }
    
    private ClientHttpRequestInterceptor loggingInterceptor() {
        return (request, body, execution) -> {
            log.debug("Request: {} {}", request.getMethod(), request.getURI());
            var response = execution.execute(request, body);
            log.debug("Response: {} {}", response.getStatusCode(), response.getStatusText());
            return response;
        };
    }
}
```

### NebulaAIClient.java (간소화)
```java
package com.example.client;

import com.example.dto.response.*;
import com.example.exception.NebulaAIException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

@Slf4j
@Component
@RequiredArgsConstructor
public class NebulaAIClient {
    
    private final RestTemplate nebulaAIRestTemplate;
    
    @Value("${nebula.ai.base-url}")
    private String baseUrl;
    
    // 👤 사용자 프로필 조회
    public UserProfileResponse getUserProfile(Long userId, boolean includeMetadata) {
        String url = String.format("%s/api/v1/profiles/%d?include_metadata=%s", 
            baseUrl, userId, includeMetadata);
        
        try {
            UserProfileResponse response = nebulaAIRestTemplate.getForObject(url, UserProfileResponse.class);
            log.info("✅ 사용자 프로필 조회 성공: userId={}", userId);
            return response;
        } catch (HttpClientErrorException.NotFound e) {
            log.warn("⚠️ 사용자 프로필을 찾을 수 없음: userId={}", userId);
            throw new UserNotFoundException("사용자 프로필을 찾을 수 없습니다: " + userId);
        } catch (Exception e) {
            log.error("❌ 사용자 프로필 조회 실패: userId={}", userId, e);
            throw new NebulaAIException("사용자 프로필 조회 실패", e);
        }
    }
    
    // 👥 유사 사용자 조회
    public SimilarUsersResponse getSimilarUsers(Long userId, int limit, double minSimilarity) {
        String url = String.format("%s/api/v1/profiles/%d/similar?limit=%d&min_similarity=%.2f",
            baseUrl, userId, limit, minSimilarity);
        
        try {
            SimilarUsersResponse response = nebulaAIRestTemplate.getForObject(url, SimilarUsersResponse.class);
            log.info("✅ 유사 사용자 조회 성공: userId={}, found={}", userId, response.getTotalFound());
            return response;
        } catch (Exception e) {
            log.error("❌ 유사 사용자 조회 실패: userId={}", userId, e);
            throw new NebulaAIException("유사 사용자 조회 실패", e);
        }
    }
    
    // 🎯 개인화 추천 조회
    public RecommendationsResponse getRecommendations(Long userId, String category, int maxAgeHours) {
        String url = String.format("%s/api/v1/profiles/%d/recommendations?category=%s&max_age_hours=%d",
            baseUrl, userId, category != null ? category : "", maxAgeHours);
        
        try {
            RecommendationsResponse response = nebulaAIRestTemplate.getForObject(url, RecommendationsResponse.class);
            log.info("✅ 추천 조회 성공: userId={}, count={}", userId, response.getRecommendations().size());
            return response;
        } catch (Exception e) {
            log.error("❌ 추천 조회 실패: userId={}", userId, e);
            throw new NebulaAIException("추천 조회 실패", e);
        }
    }
}
```

---

## 🎯 이벤트 리스너 설정 (간소화)

### NebulaAIEventListener.java
```java
package com.example.listener;

import com.example.dto.message.*;
import com.example.event.*;
import com.example.service.NebulaAIMessagePublisher;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class NebulaAIEventListener {
    
    private final NebulaAIMessagePublisher messagePublisher;
    
    // 🎯 핵심: 북마크 저장 이벤트 (가장 중요)
    @Async
    @EventListener
    public void handleBookmarkSaved(BookmarkSavedEvent event) {
        log.info("📚 북마크 저장 이벤트 수신: userId={}, starId={}", 
            event.getUserId(), event.getStarId());
        
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
        
        // 🚀 이 한 번의 호출로 Nebula AI가 모든 것을 자동 처리!
        messagePublisher.publishBookmarkSave(request);
    }
    
    // 📊 선택적: 콘텐츠 추출 이벤트
    @Async
    @EventListener
    public void handleContentExtractionNeeded(ContentExtractionEvent event) {
        log.info("🔍 콘텐츠 추출 이벤트 수신: userId={}, url={}", 
            event.getUserId(), event.getUrl());
        
        ExtractDataRequest request = ExtractDataRequest.builder()
            .userId(event.getUserId())
            .url(event.getUrl())
            .s3Key(event.getS3Key())
            .build();
        
        messagePublisher.publishExtractRequest(request);
    }
}
```

---

## ⚠️ 예외 처리

### 커스텀 예외 클래스
```java
// NebulaAIException.java
package com.example.exception;

public class NebulaAIException extends RuntimeException {
    public NebulaAIException(String message) {
        super(message);
    }
    
    public NebulaAIException(String message, Throwable cause) {
        super(message, cause);
    }
}

// UserNotFoundException.java
package com.example.exception;

public class UserNotFoundException extends NebulaAIException {
    public UserNotFoundException(String message) {
        super(message);
    }
}

// MessagePublishException.java
package com.example.exception;

public class MessagePublishException extends NebulaAIException {
    public MessagePublishException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

### GlobalExceptionHandler.java
```java
package com.example.exception;

import com.example.dto.common.ErrorResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(UserNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleUserNotFound(UserNotFoundException e) {
        log.warn("사용자를 찾을 수 없음: {}", e.getMessage());
        
        ErrorResponse response = ErrorResponse.builder()
            .message(e.getMessage())
            .errorCode("USER_NOT_FOUND")
            .build();
        
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(response);
    }
    
    @ExceptionHandler(MessagePublishException.class)
    public ResponseEntity<ErrorResponse> handleMessagePublishException(MessagePublishException e) {
        log.error("메시지 발송 실패: {}", e.getMessage(), e);
        
        ErrorResponse response = ErrorResponse.builder()
            .message("메시지 발송에 실패했습니다")
            .errorCode("MESSAGE_PUBLISH_FAILED")
            .details(Map.of("originalMessage", e.getMessage()))
            .build();
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }
    
    @ExceptionHandler(NebulaAIException.class)
    public ResponseEntity<ErrorResponse> handleNebulaAIException(NebulaAIException e) {
        log.error("Nebula AI 연동 오류: {}", e.getMessage(), e);
        
        ErrorResponse response = ErrorResponse.builder()
            .message("AI 서비스 연동 중 오류가 발생했습니다")
            .errorCode("NEBULA_AI_ERROR")
            .details(Map.of("originalMessage", e.getMessage()))
            .build();
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }
}
```

---

## 🧪 테스트 설정

### application-test.yml
```yaml
spring:
  rabbitmq:
    host: localhost
    port: 5672
    username: guest
    password: guest

nebula:
  ai:
    base-url: http://localhost:8000
    timeout: 10
    queues:
      bookmark-save: test_bookmark_save
      extract-request: test_extract_request

logging:
  level:
    com.example.nebula: DEBUG
    org.springframework.amqp: DEBUG
```

### NebulaAIMessagePublisherTest.java
```java
package com.example.service;

import com.example.dto.message.BookmarkSaveRequest;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.rabbit.test.TestRabbitTemplate;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

import javax.inject.Inject;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.yml")
class NebulaAIMessagePublisherTest {
    
    @Inject
    private NebulaAIMessagePublisher messagePublisher;
    
    @Inject
    private TestRabbitTemplate testRabbitTemplate;
    
    @Test
    void 북마크_저장_메시지_발송_테스트() {
        // Given
        BookmarkSaveRequest request = BookmarkSaveRequest.builder()
            .userId(123L)
            .starId("star_456")
            .s3Key("test/path")
            .title("테스트 북마크")
            .url("https://example.com")
            .build();
        
        // When
        messagePublisher.publishBookmarkSave(request);
        
        // Then
        assertThat(testRabbitTemplate.getReceivedMessages("test_bookmark_save")).hasSize(1);
    }
}
```

---

## 📋 간소화된 설정 체크리스트

### ✅ 필수 설정 항목

- [ ] Maven/Gradle 의존성 추가
- [ ] application.yml 환경 설정
- [ ] RabbitMQ 연결 설정
- [ ] **북마크 저장 큐 설정** (가장 중요)
- [ ] 메시지 발송 서비스 구현
- [ ] REST API 클라이언트 구현
- [ ] 북마크 저장 이벤트 리스너 구현
- [ ] 예외 처리 설정

### 🔧 선택 설정 항목

- [ ] 데이터 추출 큐 설정
- [ ] 모니터링 및 헬스체크
- [ ] 테스트 환경 구성

### 🔧 환경 변수

```properties
# application.properties (최소 설정)
spring.rabbitmq.host=${RABBITMQ_HOST:localhost}
spring.rabbitmq.port=${RABBITMQ_PORT:5672}
spring.rabbitmq.username=${RABBITMQ_USERNAME:guest}
spring.rabbitmq.password=${RABBITMQ_PASSWORD:guest}

nebula.ai.base-url=${NEBULA_AI_BASE_URL:http://localhost:8000}
nebula.ai.queues.bookmark-save=bookmark_save
```

---

## 🚀 **핵심 포인트**

1. **최소한의 설정**: 북마크 저장 큐만 설정하면 기본 연동 완료
2. **자동 처리**: 북마크 저장 → Nebula AI가 모든 분석/업데이트 자동 처리
3. **간단한 연동**: 복잡한 프로필 관리 로직 불필요
4. **조회 중심**: 완성된 데이터를 API로 조회하는 용도

이제 스프링부트 애플리케이션에서 Nebula AI 시스템과 **간단하고 효율적으로** 연동할 수 있습니다! 🚀 