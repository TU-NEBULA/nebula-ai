# 🔍 Nebula AI 성능 프로파일링 가이드

## 개요

Nebula AI 프로젝트는 **py-spy**를 사용한 성능 프로파일링 시스템을 제공합니다.  
Docker 사이드카 방식으로 구현되어 애플리케이션 코드 수정 없이 실시간 성능 분석이 가능합니다.

## 🚀 빠른 시작

### 1. 기본 프로파일링 (30초)
```bash
make profile
```

### 2. 빠른 프로파일링 (10초)
```bash
make profile-quick
```

### 3. 결과 확인
```bash
make profile-list    # 목록 확인
make profile-open    # 브라우저에서 최신 결과 열기
```

---

## 📊 프로파일링 명령어 전체 목록

### 기본 프로파일링
| 명령어 | 설명 | 시간 | 출력 형식 |
|--------|------|------|-----------|
| `make profile` | 기본 프로파일링 | 30초 | SVG flamegraph |
| `make profile-quick` | 빠른 프로파일링 | 10초 | SVG flamegraph |
| `make profile-top` | 실시간 모니터링 | 무제한 | 터미널 출력 |

### 고급 프로파일링
| 명령어 | 설명 | 특징 |
|--------|------|------|
| `make profile-load` | 부하 테스트 + 프로파일링 | 100회 API 요청과 함께 60초 프로파일링 |
| `make profile-detailed` | 상세 프로파일링 | speedscope 형식 JSON 출력 |
| `make profile-gil` | GIL 경합 분석 | Python GIL 병목 지점 분석 |
| `make profile-api ENDPOINT=/path` | 특정 API 프로파일링 | 지정된 엔드포인트에 부하 + 프로파일링 |

### 결과 관리
| 명령어 | 설명 |
|--------|------|
| `make profile-list` | 프로파일 결과 목록 표시 |
| `make profile-open` | 최신 결과 브라우저에서 열기 (macOS) |
| `make profile-clean` | 모든 프로파일 결과 삭제 |

---

## 🎯 사용 시나리오별 가이드

### 1. 일반적인 성능 분석
```bash
# 1단계: 기본 프로파일링으로 전체적인 병목 파악
make profile

# 2단계: 결과 확인
make profile-open

# 3단계: 필요시 더 상세한 분석
make profile-detailed
```

### 2. API 엔드포인트별 분석
```bash
# 채팅 API 분석
make profile-api ENDPOINT=/chat/stream

# 추천 API 분석  
make profile-api ENDPOINT=/recommendations

# 프로필 API 분석
make profile-api ENDPOINT=/profile
```

### 3. 부하 상황에서의 성능 분석
```bash
# 부하 테스트와 함께 프로파일링
make profile-load

# 실시간 모니터링 (별도 터미널에서)
make profile-top
```

### 4. GIL 병목 분석 (멀티스레딩 이슈)
```bash
# GIL 경합 상황 분석
make profile-gil
```

---

## 📂 결과 파일 구조

```
profiles/
├── baseline/              # 기본 프로파일링 결과
├── load_test/             # 부하 테스트 결과  
├── services/              # 서비스별 분석 결과
├── analysis/              # 분석 리포트
├── detailed/              # 상세 분석 결과 (JSON)
├── baseline_1751524550.svg     # 기본 프로파일링 flamegraph
├── quick_1751525364.svg        # 빠른 프로파일링 결과
├── load_test_1751525500.svg    # 부하 테스트 결과
└── gil_contention_1751525600.svg # GIL 분석 결과
```

---

## 🔍 Flamegraph 읽는 방법

### 1. 기본 구조
- **X축**: 시간이 아닌 **스택 깊이**
- **Y축**: **함수 호출 스택**
- **색상**: 함수별 구분 (의미 없음)
- **넓이**: **실행 시간 비율**

### 2. 분석 요령
1. **가장 넓은 박스** → 가장 많은 시간을 소모하는 함수
2. **높은 스택** → 깊은 호출 체인 (복잡도 높음)
3. **평평한 부분** → CPU 집약적 작업
4. **클릭 가능** → 확대/축소로 상세 분석

### 3. 주의사항
- **샘플링 기반** → 100% 정확하지 않음
- **I/O 대기 시간** → 샘플링되지 않을 수 있음
- **짧은 함수** → 놓칠 수 있음

---

## ⚙️ 기술적 구현 세부사항

### Docker 사이드카 아키텍처
```yaml
# docker-compose.yml
profiler:
  image: python:3.11-slim
  pid: "host"              # 호스트 PID 네임스페이스 공유
  privileged: true         # ptrace 권한
  profiles: [profiling]    # 필요시에만 실행
```

### 권한 설정
```yaml
web:
  cap_add: [SYS_PTRACE]    # ptrace 시스템콜 허용
  security_opt:
    - seccomp:unconfined   # seccomp 제한 해제
```

### py-spy 설치 및 실행
```bash
# 컨테이너 내부에서 실행되는 명령어
pip install py-spy > /dev/null 2>&1
py-spy record -o /profiles/result.svg --pid $PID -d 30
```

---

## 🔧 문제 해결

### 1. "컨테이너가 실행 중이지 않습니다" 오류
```bash
# 해결방법: 애플리케이션 컨테이너 시작
make start
docker ps | grep nebula-ai  # 상태 확인
```

### 2. 권한 오류 (Permission denied)
```bash
# 해결방법: Docker Compose 재시작
make stop
make start
```

### 3. 프로파일 결과가 없음
```bash
# 디렉토리 확인
ls -la profiles/

# 수동으로 디렉토리 생성
make profile-setup
```

### 4. 사이드카 컨테이너 Created 상태
- **정상 상태입니다!** 
- 프로파일링 완료 후 자동으로 삭제됨
- `docker container prune -f`로 정리 가능

---

## 📈 성능 최적화 워크플로우

### 1. 현재 상태 파악
```bash
make profile          # 기본 프로파일링
make profile-open     # 결과 확인
```

### 2. 병목 지점 식별
- Flamegraph에서 가장 넓은 박스 찾기
- 높은 CPU 사용률 함수 확인
- I/O 대기 vs CPU 집약적 작업 구분

### 3. 상세 분석
```bash
# 특정 API 집중 분석
make profile-api ENDPOINT=/bottleneck-endpoint

# GIL 이슈 확인
make profile-gil
```

### 4. 최적화 후 검증
```bash
# 최적화 전후 비교
make profile-load     # 부하 상황에서 재측정
```

---

## 💡 팁과 권장사항

### 1. 프로파일링 타이밍
- **개발 중**: `profile-quick` (10초)로 빠른 확인
- **최적화 전**: `profile` (30초)로 정확한 분석  
- **배포 전**: `profile-load`로 부하 상황 테스트

### 2. 결과 보관
- 중요한 벤치마크는 별도 보관
- Git에는 커밋하지 말고 외부 저장소 활용
- 버전별 성능 변화 추적

### 3. 팀 공유
- 성능 이슈 발견 시 SVG 파일 공유
- 최적화 전후 비교 결과 문서화
- 정기적인 성능 모니터링 실시

---

## 🔗 관련 문서

- [Docker Compose 설정](../docker-compose.yml)
- [성능 모니터링 가이드](./monitoring_guide.md)
- [py-spy 공식 문서](https://github.com/benfred/py-spy)
- [Flamegraph 해석 가이드](https://www.brendangregg.com/flamegraphs.html)

---

## 📞 지원

프로파일링 관련 문제나 질문이 있으면:

1. **도움말 확인**: `make profile-help`
2. **이슈 확인**: 기존 프로파일 결과와 비교
3. **팀 문의**: 성능 최적화 관련 논의

---

*마지막 업데이트: 2024년 1월* 