# 사용자 프로필 데이터 업데이트 프로세스

## 개요

Nebula AI의 사용자 프로필 업데이트 시스템은 사용자의 행동과 상호작용을 실시간으로 추적하여 개인화된 추천과 사용자 경험을 제공하기 위한 최적화된 시스템입니다. 이 문서는 Task #32에서 구현된 "사용자 프로필 업데이트 시스템 최적화"를 중심으로 전체 업데이트 과정을 상세히 설명합니다.

## 시스템 아키텍처

### CQRS(Command Query Responsibility Segregation) 패턴

사용자 프로필 시스템은 CQRS 아키텍처를 기반으로 구성되어 있습니다:

- **Command Side (쓰기)**: 프로필 업데이트 요청을 RabbitMQ를 통해 처리
- **Query Side (읽기)**: FastAPI를 통한 프로필 조회 API 제공
- **Event Sourcing**: 모든 사용자 행동을 이벤트로 추적 및 저장

### 핵심 구성요소

1. **실시간 증분 업데이트 시스템**
2. **지능형 배치 업데이트 시스템**
3. **적응형 업데이트 스케줄링**
4. **성능 모니터링 시스템**

## 실시간 업데이트 프로세스

### 1. 북마크 기반 실시간 업데이트

#### 이벤트 플로우
```
사용자 북마크 저장 → BookmarkEventListener → UserProfileProcessor → Redis 캐시 → PostgreSQL 업데이트
```

#### 구현 세부사항

**BookmarkEventListener (`app/listeners/user_actions.py`)**
- 북마크 생성/수정 이벤트를 실시간 감지
- 변경사항의 중요도를 판단하여 불필요한 업데이트 방지
- 콜백 시스템을 통한 확장 가능한 이벤트 처리

**UserProfileProcessor (`app/services/user_profile_processor.py`)**
- `handle_bookmark_event()` 메소드로 북마크 데이터 처리
- 북마크에서 분석 가능한 콘텐츠 추출 (제목, 설명, 카테고리, 태그, URL 도메인)
- ActivityType.BOOKMARK로 분류되어 가중치 1.5 적용

#### 데이터 처리 과정

1. **콘텐츠 추출**: 북마크에서 의미 있는 데이터 추출
2. **ActivityData 변환**: 표준화된 형태로 데이터 변환
3. **Redis 캐싱**: 원자적 연산을 위한 임시 저장
4. **벡터 업데이트**: 기존 프로필에 새로운 정보를 증분 방식으로 추가
5. **데이터베이스 저장**: PostgreSQL에 최종 저장

### 2. 채팅 세션 기반 실시간 업데이트

#### 이벤트 플로우
```
채팅 세션 완료 → ChatEventListener → UserProfileProcessor → 콘텐츠 분석 → 프로필 업데이트
```

#### 프라이버시 보호 및 콘텐츠 처리

**개인정보 마스킹**
- 이메일, 전화번호, 주소 등 개인정보 자동 마스킹
- `_clean_chat_content()` 메소드로 민감 정보 제거

**동적 가중치 계산**
- 메시지 수: 더 많은 대화일수록 높은 가중치
- 세션 시간: 긴 대화일수록 더 의미 있는 것으로 판단
- 주제 다양성: 다양한 주제를 다룬 대화일수록 높은 점수

**콘텐츠 분석**
```python
def _extract_chat_content(self, chat_data: Dict[str, Any]) -> str:
    # 채팅 메시지에서 의미 있는 콘텐츠 추출
    # 주제, 키워드, 문맥 분석
    # 개인정보 제거 후 분석용 텍스트 반환
```

## 배치 업데이트 시스템

### 일일 프로필 품질 모니터링

#### 품질 점수 계산 (`app/tasks/daily_profile_monitor.py`)

품질 점수는 5가지 차원에서 평가됩니다:

1. **완성도 (Completeness)**: 프로필 데이터의 충실도
2. **최신성 (Recency)**: 마지막 업데이트로부터의 시간
3. **벡터 강도 (Vector Strength)**: 프로필 벡터의 품질
4. **활동 수준 (Activity Level)**: 사용자 활동 빈도
5. **다양성 (Diversity)**: 사용자 관심사의 다양성

#### 품질 기준 임계값

- **즉시 업데이트**: 품질 점수 ≤ 0.3
- **업데이트 권장**: 품질 점수 ≤ 0.5
- **양호**: 품질 점수 > 0.5

#### 자동 업데이트 실행

**DailyProfileMonitor 클래스**
```python
class DailyProfileMonitor:
    def __init__(self, db_session, profile_processor):
        self.db_session = db_session
        self.profile_processor = profile_processor
        self.quality_calculator = ProfileQualityCalculator()
    
    async def run_quality_check(self) -> QualityReport:
        # 모든 사용자 프로필의 품질 검사
        # 임계값 이하 프로필 자동 업데이트
        # 상세 보고서 생성
```

### 주간 전체 재계산 시스템

주간 배치 시스템은 현재 고도화 단계에서 별도 작업으로 계획되어 있으며, 다음과 같은 기능을 포함할 예정입니다:

- 머신러닝 기반 업데이트 빈도 예측
- 스마트 배치 업데이트 우선순위 지정
- 시스템 부하와 업데이트 긴급성의 균형 조절

## API 통합 및 CQRS 패턴

### ProfileAPIAdapter (`app/adapters/profile_api_adapter.py`)

CQRS 아키텍처와의 완전한 통합을 위해 ProfileAPIAdapter가 구현되었습니다:

#### 핵심 기능

1. **RabbitMQ 메시지 발행**: 모든 프로필 업데이트를 Command Side로 전송
2. **배치 업데이트 지원**: 여러 사용자의 동시 업데이트 처리
3. **연결 관리**: RabbitMQ 연결 생명주기 관리
4. **장애 복구**: 메시지 지속성, TTL, 오류 복구 메커니즘

#### 메시지 구조
```json
{
  "user_id": "string",
  "activity_data": {
    "type": "BOOKMARK | CHAT",
    "content": "string",
    "weight": 1.5,
    "timestamp": "2024-01-01T00:00:00Z"
  },
  "force_recalculation": false,
  "metadata": {
    "source": "profile_optimization_system",
    "quality_score": 0.7
  }
}
```

### 이벤트 리스너 통합

기존 이벤트 리스너들이 API 어댑터를 기본적으로 사용하도록 업데이트되었습니다:

- **BookmarkEventListener**: RabbitMQ 우선, 실패 시 직접 처리기 호출
- **ChatEventListener**: 채팅 완료 이벤트를 RabbitMQ로 처리
- **하위 호환성**: 기존 직접 호출 방식도 지원 (경고 메시지와 함께)

## 성능 모니터링 및 메트릭

### 수집되는 메트릭

1. **업데이트 지연시간**: 이벤트 발생부터 프로필 업데이트까지의 시간
2. **리소스 사용률**: CPU, 메모리, 네트워크 사용량
3. **프로필 품질 지표**: 신선도, 완성도, 다양성 점수
4. **처리량**: 시간당 처리되는 이벤트 수
5. **오류율**: 실패한 업데이트의 비율

### Celery Beat 스케줄링

일일 품질 모니터링은 Celery Beat을 통해 자동화됩니다:

```python
# 매일 오전 2시에 실행
CELERY_BEAT_SCHEDULE = {
    'daily-profile-quality-check': {
        'task': 'app.tasks.daily_profile_monitor.run_daily_quality_check_task',
        'schedule': crontab(hour=2, minute=0),
        'options': {
            'queue': 'profile_monitor',
            'expires': 21600  # 6시간 후 만료
        }
    }
}
```

## 데이터 플로우 다이어그램

```
[사용자 행동] 
    ↓
[이벤트 리스너]
    ↓
[ProfileAPIAdapter]
    ↓
[RabbitMQ Command Queue]
    ↓
[UserProfileProcessor]
    ↓
[Redis 캐시]
    ↓
[PostgreSQL 업데이트]
    ↓
[Query Side API]
    ↓
[사용자 인터페이스]
```

## 테스트 전략

### 단위 테스트
- 각 업데이트 구성요소의 개별 기능 테스트
- 증분 업데이트 로직 검증
- 배치 업데이트 우선순위 알고리즘 테스트
- 적응형 스케줄링 시뮬레이션

### 통합 테스트
- 사용자 행동부터 프로필 업데이트까지의 E2E 플로우
- 실시간 및 배치 시스템 간의 상호작용
- 동시 업데이트 상황에서의 데이터베이스 일관성
- User Profile API와의 통합 검증

### 성능 테스트
- 다양한 부하 상황에서의 업데이트 지연시간 벤치마킹
- 대량 사용자 활동 시뮬레이션
- 최대 처리량 및 리소스 사용률 측정
- 확장성 검증

## 확장성 및 향후 계획

### 현재 구현된 기능 (완료)
- ✅ 실시간 북마크 프로필 업데이트
- ✅ 실시간 채팅 세션 프로필 업데이트  
- ✅ 일일 프로필 품질 모니터링 및 자동 업데이트
- ✅ User Profile API와의 CQRS 통합

### 향후 구현 예정 (연기됨)
- 🔄 주간 전체 재계산 배치 시스템
- 🔄 사용자별 맞춤형 업데이트 스케줄러
- 🔄 프로필 품질 기반 동적 업데이트 빈도 조절
- 🔄 성능 메트릭 수집 및 Grafana 대시보드
- 🔄 업데이트 전략 분석 및 자동 조정 시스템

### 확장 가능성
- **새로운 이벤트 타입**: 이벤트 리스너 프레임워크로 쉽게 추가 가능
- **AI 모델 통합**: 사용자 행동 예측 및 개인화 알고리즘 적용
- **다중 테넌트 지원**: 조직별 분리된 프로필 관리
- **실시간 추천**: 업데이트된 프로필 기반 즉시 추천 생성

## 보안 및 프라이버시

### 개인정보 보호
- 채팅 데이터에서 자동 개인정보 마스킹
- 프로필 데이터 암호화 저장
- 최소한의 데이터만 수집 및 저장

### 접근 제어
- 사용자별 프로필 접근 권한 관리
- API 호출 인증 및 권한 부여
- 감사 로그를 통한 모든 업데이트 추적

## 결론

Nebula AI의 사용자 프로필 업데이트 시스템은 실시간 반응성과 장기적 데이터 일관성을 모두 보장하는 최적화된 아키텍처를 제공합니다. CQRS 패턴을 통한 확장 가능한 설계와 지능형 품질 모니터링을 통해 사용자에게 최상의 개인화 경험을 제공할 수 있는 기반을 마련했습니다.

현재 구현된 핵심 기능들은 안정적으로 운영되고 있으며, 향후 계획된 고도화 기능들을 통해 더욱 정교하고 효율적인 시스템으로 발전할 예정입니다. 