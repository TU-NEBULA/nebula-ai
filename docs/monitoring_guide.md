# Nebula AI 모니터링 시스템 가이드

이 가이드는 Nebula AI 애플리케이션의 모니터링 시스템 설정 및 사용법을 설명합니다.

## 📋 목차

1. [개요](#개요)
2. [시스템 구성](#시스템-구성)
3. [설치 및 설정](#설치-및-설정)
4. [사용법](#사용법)
5. [대시보드 가이드](#대시보드-가이드)
6. [메트릭 설명](#메트릭-설명)
7. [문제 해결](#문제-해결)
8. [고급 설정](#고급-설정)

## 개요

Nebula AI 모니터링 시스템은 다음 구성요소들로 이루어져 있습니다:

- **Prometheus**: 메트릭 수집 및 저장
- **Grafana**: 시각화 대시보드
- **Node Exporter**: 시스템 메트릭 수집
- **FastAPI Instrumentator**: 애플리케이션 메트릭 수집

## 시스템 구성

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nebula AI     │    │   Prometheus    │    │    Grafana      │
│   Application   │───▶│   (메트릭 수집)   │───▶│   (시각화)       │
│   (:8001)       │    │   (:9090)       │    │   (:3000)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       ▲
         │                       │
         ▼                       │
┌─────────────────┐    ┌─────────────────┐
│    메트릭        │    │  Node Exporter  │
│   엔드포인트      │    │   (시스템 메트릭)  │
│  (/metrics)     │    │   (:9100)       │
└─────────────────┘    └─────────────────┘
```

## 설치 및 설정

### 1. 의존성 설치

```bash
# 프로메테우스 관련 패키지 설치
pipenv install prometheus-client prometheus-fastapi-instrumentator

# 또는 기존 환경에서
pip install prometheus-client prometheus-fastapi-instrumentator
```

### 2. 환경 변수 설정

`.env` 파일에 모니터링 관련 환경 변수를 추가합니다:

```bash
# 모니터링 설정
ENABLE_METRICS=true
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=nebula2024!
METRICS_COLLECTION_INTERVAL=15
```

### 3. 모니터링 시스템 시작

```bash
# 전체 시스템 (애플리케이션 + 모니터링) 시작
make full-monitoring

# 또는 단계별 시작
make dev-start          # 애플리케이션 시작
make monitoring-start   # 모니터링 시스템 시작
```

## 사용법

### 기본 명령어

```bash
# 모니터링 시스템 시작
make monitoring-start

# 모니터링 시스템 중지
make monitoring-stop

# 모니터링 시스템 재시작
make monitoring-restart

# 전체 시스템 상태 확인
make monitoring-status

# 로그 확인
make monitoring-logs

# 메트릭 엔드포인트 테스트
make metrics-check
```

### 웹 인터페이스 접속

- **Grafana 대시보드**: http://localhost:3000
  - 사용자명: `admin`
  - 비밀번호: `nebula2024!`

- **Prometheus 웹 UI**: http://localhost:9090

- **애플리케이션 메트릭**: http://localhost:8001/metrics

- **Node Exporter 메트릭**: http://localhost:9100/metrics

### 시스템 검증

모니터링 시스템이 올바르게 작동하는지 확인하려면:

```bash
# 자동 테스트 실행
python scripts/test_monitoring.py

# 또는 수동 확인
curl http://localhost:8001/metrics       # 애플리케이션 메트릭
curl http://localhost:9090/-/healthy     # 프로메테우스 상태
curl http://localhost:3000/api/health    # 그라파나 상태
```

## 대시보드 가이드

### Nebula AI 메인 대시보드

Grafana에 로그인 후 "Nebula AI - 애플리케이션 모니터링" 대시보드를 확인할 수 있습니다.

#### 주요 패널들:

1. **HTTP 요청 수 (시간당)**: 시간당 총 HTTP 요청 수
2. **평균 응답 시간**: 모든 엔드포인트의 평균 응답 시간
3. **에러율**: 4xx, 5xx 응답의 비율
4. **메모리 사용량**: 애플리케이션 메모리 사용량
5. **HTTP 요청 트래픽**: 시간별 요청 트렌드
6. **응답 시간 분포**: 50th, 95th, 99th percentile 응답 시간
7. **북마크 작업**: 북마크 관련 작업 메트릭
8. **추천 요청**: 추천 시스템 메트릭
9. **시스템 리소스**: CPU 및 메모리 사용률
10. **데이터베이스 쿼리 시간**: DB 쿼리 성능
11. **외부 API 호출 시간**: 외부 서비스 호출 시간

### 알림 설정

Grafana에서 알림을 설정하려면:

1. Dashboard → Panel → Edit
2. Alert 탭 선택
3. 조건 설정 (예: 응답시간 > 500ms)
4. 알림 채널 설정 (Slack, Email 등)

## 메트릭 설명

### 애플리케이션 메트릭

| 메트릭 이름 | 타입 | 설명 |
|------------|------|------|
| `http_requests_total` | Counter | 총 HTTP 요청 수 |
| `http_request_duration_seconds` | Histogram | HTTP 요청 처리 시간 |
| `memory_usage_bytes` | Gauge | 메모리 사용량 (바이트) |
| `cpu_usage_percent` | Gauge | CPU 사용률 (%) |
| `database_query_duration_seconds` | Histogram | 데이터베이스 쿼리 시간 |
| `external_api_duration_seconds` | Histogram | 외부 API 호출 시간 |
| `bookmark_operations_total` | Counter | 북마크 작업 수 |
| `recommendation_requests_total` | Counter | 추천 요청 수 |

### 시스템 메트릭 (Node Exporter)

| 메트릭 이름 | 설명 |
|------------|------|
| `node_cpu_seconds_total` | CPU 시간 |
| `node_memory_MemTotal_bytes` | 총 메모리 |
| `node_memory_MemAvailable_bytes` | 사용 가능한 메모리 |
| `node_filesystem_size_bytes` | 파일시스템 크기 |
| `node_network_receive_bytes_total` | 네트워크 수신 바이트 |

## 문제 해결

### 일반적인 문제들

#### 1. 메트릭 엔드포인트 접근 불가

```bash
# 애플리케이션 상태 확인
make dev-status

# 애플리케이션 로그 확인
make dev-logs-web

# 포트 확인
curl http://localhost:8001/health
```

#### 2. Prometheus에서 타겟을 찾을 수 없음

```bash
# Docker 네트워크 확인
docker network ls
docker network inspect nebula-ai_default

# 컨테이너 상태 확인
docker ps | grep nebula
```

#### 3. Grafana에서 데이터가 보이지 않음

1. Grafana에서 데이터소스 상태 확인:
   - Configuration → Data Sources → Prometheus
   - "Test" 버튼 클릭

2. 프로메테우스에서 메트릭 확인:
   - http://localhost:9090/targets
   - 모든 타겟이 "UP" 상태인지 확인

#### 4. 권한 문제

```bash
# Docker 볼륨 권한 확인
sudo chown -R $USER:$USER docker/monitoring/

# 로그 디렉토리 생성
mkdir -p logs
```

### 로그 확인

```bash
# 전체 모니터링 시스템 로그
make monitoring-logs

# 개별 서비스 로그
make monitoring-logs-prometheus
make monitoring-logs-grafana

# 애플리케이션 로그
make dev-logs-web
```

### 시스템 재시작

```bash
# 모니터링 시스템만 재시작
make monitoring-restart

# 전체 시스템 재시작
make stop-all
make full-monitoring

# 완전 초기화 (볼륨 포함)
make monitoring-clean
make dev-clean
make full-monitoring
```

## 고급 설정

### 1. 메트릭 커스터마이징

`app/core/monitoring.py` 파일에서 새로운 메트릭을 추가할 수 있습니다:

```python
# 새로운 메트릭 추가 예시
custom_operations = Counter(
    "custom_operations_total",
    "사용자 정의 작업 수",
    ["operation_type", "status"]
)

# 메트릭 업데이트
custom_operations.labels(
    operation_type="data_processing",
    status="success"
).inc()
```

### 2. 알림 규칙 설정

`docker/monitoring/prometheus/alerts.yml` 파일을 생성하여 알림 규칙을 설정:

```yaml
groups:
  - name: nebula-ai-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "높은 에러율 감지"
          description: "5분간 에러율이 10%를 초과했습니다"
```

### 3. 추가 Exporter 설정

더 많은 메트릭을 수집하려면 추가 Exporter를 설정할 수 있습니다:

- **PostgreSQL Exporter**: 데이터베이스 메트릭
- **Redis Exporter**: Redis 캐시 메트릭
- **RabbitMQ Exporter**: 메시지 큐 메트릭

### 4. 보안 설정

프로덕션 환경에서는 다음 보안 설정을 고려하세요:

1. **HTTPS 설정**: TLS 인증서 적용
2. **인증 설정**: Grafana OAuth 연동
3. **네트워크 분리**: 모니터링 전용 네트워크 구성
4. **방화벽 규칙**: 필요한 포트만 개방

### 5. 성능 최적화

- **Prometheus 보존 기간**: 필요에 따라 조정
- **Grafana 쿼리 최적화**: 대시보드 쿼리 성능 개선
- **메트릭 라벨 관리**: 카디널리티 제어

## 참고 자료

- [Prometheus 공식 문서](https://prometheus.io/docs/)
- [Grafana 공식 문서](https://grafana.com/docs/)
- [FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [Node Exporter](https://github.com/prometheus/node_exporter)

---

문의사항이나 문제가 있으시면 개발팀에 연락주세요. 