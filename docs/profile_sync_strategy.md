# 프로필 동기화 하이브리드 전략

## 📋 개요

사용자 AI 프로필에서 User Profile로의 업데이트를 위해 **실시간 동기화**와 **새벽 배치**를 조합한 하이브리드 접근법을 사용합니다.

## 🔄 실시간 동기화 (3시간마다)

### 📍 위치
- **파일**: `app/tasks/profile_sync_task.py`
- **태스크명**: `tasks.profile_sync_realtime`
- **스케줄**: 매 3시간마다 (00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00)

### 🎯 목적
- AI 프로필 변경사항을 빠르게 User Profile에 반영
- 사용자 경험의 실시간성 향상
- 경량화된 데이터 동기화

### ⚡ 주요 특징
- **활성 사용자 우선**: 24시간/7일 내 활동 기준으로 우선순위 부여
- **선택적 처리**: 변경된 사용자만 대상으로 효율성 극대화
- **배치 처리**: 최대 200명씩 배치 단위로 안전한 처리
- **부하 분산**: 3시간 간격으로 서버 부하 분산

### 🔍 동기화 조건
```sql
WHERE (
    -- AI Profile이 User Profile보다 최근에 업데이트된 경우
    up.id IS NULL OR 
    uap.updated_at > up.last_updated_at OR
    -- 또는 3시간 이상 동기화되지 않은 경우
    up.last_updated_at < NOW() - INTERVAL '3 hours'
)
AND uap.total_chat_sessions > 0  -- 실제 활동이 있는 사용자만
ORDER BY 
    priority_level ASC,  -- 활성 사용자 우선
    uap.updated_at DESC
```

## 📊 새벽 배치 (매일 새벽 2시)

### 📍 위치
- **파일**: `app/tasks/daily_profile_monitor.py`
- **태스크명**: `tasks.run_daily_quality_check`
- **스케줄**: 매일 새벽 2시

### 🎯 목적
- 전체 프로필 품질 분석 및 리포팅
- 문제 프로필 식별 및 집중 관리
- 시스템 전체 건강성 모니터링

### 📈 주요 특징
- **품질 점수 계산**: 완성도, 최신성, 벡터 강도, 활동 수준, 다양성
- **상세 리포팅**: 품질 분포, 개선 권장사항, 성공률 추적
- **자동 수정**: 낮은 품질 프로필 자동 업데이트
- **모니터링**: 시스템 전체 성능 분석

### 🏆 품질 평가 기준
- **Critical (0.0-0.3)**: 즉시 업데이트 필요
- **Low (0.3-0.5)**: 업데이트 권장  
- **Medium (0.5-0.7)**: 보통
- **High (0.7-0.85)**: 우수
- **Excellent (0.85-1.0)**: 최우수

## 🤝 역할 분담

| 구분 | 실시간 동기화 | 새벽 배치 |
|------|---------------|-----------|
| **주기** | 3시간마다 | 매일 새벽 2시 |
| **대상** | 변경된 사용자 | 전체 사용자 |
| **목적** | 빠른 데이터 동기화 | 품질 분석 + 관리 |
| **처리방식** | 경량화, 선택적 | 전면적, 상세 분석 |
| **성능** | 실시간성 우선 | 정확성 우선 |
| **부하** | 분산 처리 | 집중 처리 |

## 🚀 장점

### 💫 실시간성
- 사용자 활동에 3시간 내 반응
- 개인화 추천의 즉시성 향상

### ⚖️ 안정성  
- 새벽 배치로 전체 시스템 품질 보장
- 문제 프로필 자동 감지 및 수정

### 🎯 효율성
- 활성 사용자 우선 처리
- 변경된 데이터만 선택적 동기화

### 📊 모니터링
- 상세한 품질 리포트
- 시스템 건강성 지속 추적

## 🔧 설정 및 실행

### Celery Beat 스케줄러 시작
```bash
# Celery worker 시작
celery -A app.core.celery_worker worker --loglevel=info

# Celery beat 스케줄러 시작 (스케줄 실행)
celery -A app.core.celery_worker beat --loglevel=info
```

### 수동 실행 (테스트/디버깅)
```bash
# 실시간 동기화 수동 실행
python -c "from app.tasks.profile_sync_task import run_profile_sync; import asyncio; asyncio.run(run_profile_sync())"

# 새벽 배치 수동 실행  
python -c "from app.tasks.daily_profile_monitor import run_daily_quality_check_task; print(run_daily_quality_check_task())"
```

## 📈 모니터링 방법

### 실시간 동기화 모니터링
```python
# 로그 확인
tail -f logs/nebula_ai.log | grep "실시간 프로필 동기화"

# Celery 태스크 상태 확인
celery -A app.core.celery_worker inspect active
```

### 새벽 배치 모니터링  
```python
# 품질 리포트 확인
tail -f logs/nebula_ai.log | grep "품질 체크"

# 상세 품질 분석
python -c "from app.tasks.daily_profile_monitor import get_low_quality_profiles; import asyncio; print(asyncio.run(get_low_quality_profiles()))"
```

## ⚠️ 주의사항

1. **Celery Beat 필수**: 스케줄링을 위해 Celery Beat이 반드시 실행되어야 합니다
2. **데이터베이스 부하**: 새벽 2시 배치 시 DB 성능 모니터링 필요
3. **로그 모니터링**: 실패한 동기화나 품질 문제 조기 발견을 위한 로그 확인
4. **백업 전략**: 중요한 프로필 데이터 변경 전 백업 권장

## 🔄 향후 개선 방안

1. **적응형 스케줄링**: 사용자 활동 패턴에 따른 동적 스케줄 조정
2. **성능 최적화**: 벡터 계산 캐싱 및 배치 크기 자동 조정  
3. **실시간 모니터링**: 대시보드를 통한 실시간 상태 확인
4. **장애 복구**: 자동 재시도 및 장애 알림 시스템 강화 