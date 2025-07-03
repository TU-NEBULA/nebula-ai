# ============================================================================
# Nebula AI - Makefile
# ============================================================================

# ============================================================================
# 📦 기본 개발 명령어 (가장 자주 사용)
# ============================================================================

.PHONY: help-lint
help-lint:
	@echo "🔍 린트 관련 명령어:"
	@echo "  make lint                     - 전체 프로젝트 린트 검사"
	@echo "  make lint-file FILE=파일경로   - 특정 파일 린트 검사"
	@echo "  make lint-fix-file FILE=파일경로 - 특정 파일 자동 수정 후 린트 검사"
	@echo "  ./scripts/lint_file.sh 파일경로 - 스크립트로 파일 린트 (기본: 검사만)"
	@echo "  ./scripts/lint_file.sh --fix 파일경로 - 스크립트로 파일 자동 수정"
	@echo ""
	@echo "예시:"
	@echo "  make lint-file FILE=app/main.py"
	@echo "  ./scripts/lint_file.sh app/main.py"
	@echo "  ./scripts/lint_file.sh --fix app/main.py"

.PHONY: dev
dev: test stop build start
	@echo "🎉 개발 환경이 준비되었습니다!"
	@echo "🌐 API: http://localhost:8001"
	@echo "📚 문서: http://localhost:8001/docs"

.PHONY: dev-quick
dev-quick: stop build-quick start
	@echo "⚡ 빠른 개발 환경이 준비되었습니다!"

.PHONY: dev-no-test
dev-no-test: stop build start

.PHONY: run-local
run-local:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# ============================================================================
# 🏗️ 환경 관리 명령어
# ============================================================================

.PHONY: install
install:
	pipenv install --dev

.PHONY: freeze
freeze:
	pipenv requirements > requirements.txt

.PHONY: start
start:
	docker-compose up -d

.PHONY: stop
stop: 
	docker-compose down

.PHONY: build
build: fix-buildx
	@echo "🔨 이미지 빌드 (캐시 무시)..."
	docker-compose build --no-cache

.PHONY: build-quick
build-quick: fix-buildx  
	@echo "⚡ 빠른 빌드 (캐시 사용)..."
	DOCKER_BUILDKIT=1 docker-compose build

.PHONY: restart
restart: stop build start

.PHONY: status
status:
	@echo "📊 서비스 상태..."
	docker-compose ps

.PHONY: logs
logs:
	@echo "📋 서비스 로그..."
	docker-compose logs -f

.PHONY: logs-web
logs-web:
	@echo "📋 웹 서비스 로그..."
	docker-compose logs -f web

.PHONY: logs-celery
logs-celery:
	@echo "📋 Celery 워커 로그..."
	docker-compose logs -f celery_worker

.PHONY: shell
shell:
	@echo "💻 웹 컨테이너 쉘 접속..."
	docker-compose exec web bash

.PHONY: shell-celery
shell-celery:
	@echo "💻 Celery 컨테이너 쉘 접속..."
	docker-compose exec celery_worker bash

# ============================================================================
# 🧪 테스트 명령어
# ============================================================================

.PHONY: test
test:
	pytest tests --disable-warnings -v

.PHONY: test-all
test-all: test-unit test-manual test-performance
	@echo "🎉 모든 테스트 완료!"

.PHONY: test-unit
test-unit:
	@echo "🧪 단위 테스트 실행..."
	pytest tests/ -v --disable-warnings

.PHONY: test-manual
test-manual:
	@echo "🔧 수동 테스트 실행..."
	python tests/manual/consumer_test.py
	python tests/manual/task_test.py

.PHONY: test-performance
test-performance:
	@echo "⚡ 성능 테스트 실행..."
	python tests/performance/bookmark_performance_test.py

.PHONY: test-cov 
test-cov:
	pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-report=html \
		tests

.PHONY: test-cov-html
test-cov-html: test-cov
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open htmlcov/index.html; \
	elif command -v open >/dev/null 2>&1; then \
		open htmlcov/index.html; \
	else \
		echo "htmlcov/index.html 을 브라우저로 열어 확인하세요."; \
	fi

.PHONY: test-env-start
test-env-start:
	@echo "🚀 테스트 환경 설정..."
	docker-compose -f docker/test/docker-compose.test.yml up -d
	@echo "⏳ 서비스 준비 대기 중..."
	sleep 10
	python scripts/test/setup_dev_environment.py

.PHONY: test-env-stop
test-env-stop:
	@echo "🧹 테스트 환경 정리..."
	docker-compose -f docker/test/docker-compose.test.yml down

.PHONY: test-env-status
test-env-status:
	@echo "📊 테스트 서비스 상태 확인..."
	docker-compose -f docker/test/docker-compose.test.yml ps

.PHONY: test-env-logs
test-env-logs:
	@echo "📋 테스트 서비스 로그 확인..."
	docker-compose -f docker/test/docker-compose.test.yml logs

# ============================================================================
# 🔍 코드 품질 명령어
# ============================================================================

PYLINTRC := .pylintrc
FASTAPI_SRC := app

.PHONY: lint
lint:
	@echo "=== Pylint 검사 시작 ==="
	@if [ -f $(PYLINTRC) ]; then \
	  pylint $(FASTAPI_SRC) --rcfile=$(PYLINTRC); \
	else \
	  pylint $(FASTAPI_SRC); \
	fi

.PHONY: format
format:
	@echo "=== Trailing whitespace 제거 ==="
	@find $(FASTAPI_SRC) -type f -name '*.py' \
	  -exec sed -i 's/[[:blank:]]\+$$//' {} +

.PHONY: lint-file
lint-file:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ 사용법: make lint-file FILE=파일경로"; \
		echo "예시: make lint-file FILE=app/main.py"; \
		exit 1; \
	fi
	@echo "🔍 $(FILE) 파일 린트 검사 중..."
	@if [ -f $(PYLINTRC) ]; then \
		pylint $(FILE) --rcfile=$(PYLINTRC); \
	else \
		pylint $(FILE); \
	fi

.PHONY: lint-fix-file
lint-fix-file:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ 사용법: make lint-fix-file FILE=파일경로"; \
		echo "예시: make lint-fix-file FILE=app/main.py"; \
		exit 1; \
	fi
	@echo "🔧 $(FILE) 파일 자동 수정 중..."
	@# autopep8로 자동 수정 (설치되어 있다면)
	@if command -v autopep8 >/dev/null 2>&1; then \
		autopep8 --in-place --aggressive --aggressive $(FILE); \
		echo "✅ autopep8 자동 수정 완료"; \
	fi
	@# isort로 import 정렬 (설치되어 있다면)
	@if command -v isort >/dev/null 2>&1; then \
		isort $(FILE); \
		echo "✅ import 정렬 완료"; \
	fi
	@# black으로 포매팅 (설치되어 있다면)
	@if command -v black >/dev/null 2>&1; then \
		black $(FILE); \
		echo "✅ black 포매팅 완료"; \
	fi
	@# 마지막에 pylint 검사
	@echo "🔍 최종 pylint 검사..."
	@if [ -f $(PYLINTRC) ]; then \
		pylint $(FILE) --rcfile=$(PYLINTRC) || true; \
	else \
		pylint $(FILE) || true; \
	fi

# ============================================================================
# 🔴 Redis 관리 명령어
# ============================================================================

.PHONY: redis-start
redis-start:
	@echo "🚀 Redis 시작..."
	docker-compose up -d redis

.PHONY: redis-stop
redis-stop:
	@echo "🛑 Redis 중지..."
	docker-compose stop redis

.PHONY: redis-restart
redis-restart:
	@echo "🔄 Redis 재시작..."
	docker-compose restart redis

.PHONY: redis-ping
redis-ping:
	@echo "🏓 Redis 연결 테스트..."
	docker exec nebula-redis-dev redis-cli -a dev_password_123 ping

.PHONY: redis-info
redis-info:
	@echo "ℹ️  Redis 정보 확인..."
	docker exec nebula-redis-dev redis-cli -a dev_password_123 info

.PHONY: redis-memory
redis-memory:
	@echo "🧠 Redis 메모리 사용량..."
	docker exec nebula-redis-dev redis-cli -a dev_password_123 info memory

.PHONY: redis-clients
redis-clients:
	@echo "👥 Redis 클라이언트 연결 상태..."
	docker exec nebula-redis-dev redis-cli -a dev_password_123 client list

.PHONY: redis-slowlog
redis-slowlog:
	@echo "🐌 Redis 슬로우 로그 (최근 10개)..."
	docker exec nebula-redis-dev redis-cli -a dev_password_123 slowlog get 10

.PHONY: redis-keys
redis-keys:
	@echo "🔑 Redis 키 목록 (최대 100개)..."
	docker exec nebula-redis-dev redis-cli -a dev_password_123 --scan --count 100

.PHONY: redis-celery-keys
redis-celery-keys:
	@echo "🔑 Celery 관련 키 목록..."
	docker exec nebula-redis-dev redis-cli -a dev_password_123 keys "celery*"

.PHONY: redis-benchmark
redis-benchmark:
	@echo "🏃‍♂️ Redis 성능 벤치마크 실행..."
	docker exec nebula-redis-dev redis-benchmark -a dev_password_123 -t set,get -n 10000 -q

.PHONY: redis-logs
redis-logs:
	@echo "📋 Redis 로그 확인..."
	docker-compose logs -f redis

.PHONY: redis-flush-dev
redis-flush-dev:
	@echo "⚠️  개발용 Redis 데이터 모두 삭제 (주의!)..."
	@read -p "정말로 모든 Redis 데이터를 삭제하시겠습니까? (y/N): " confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker exec nebula-redis-dev redis-cli -a dev_password_123 --eval "for i=0,15 do redis.call('select', i) local keys = redis.call('keys', '*') if #keys > 0 then redis.call('del', unpack(keys)) end end return 'OK'" 0; \
		echo "✅ Redis 데이터 삭제 완료"; \
	else \
		echo "❌ 취소됨"; \
	fi

# ============================================================================
# 🔍 성능 프로파일링 명령어
# ============================================================================

# 프로파일 결과 저장 디렉토리 생성
.PHONY: profile-setup
profile-setup:
	@echo "📁 프로파일 디렉토리 설정..."
	@mkdir -p profiles/{baseline,load_test,services,analysis,detailed}

# 기본 프로파일링 (30초)
.PHONY: profile
profile: profile-setup
	@echo "🔍 기본 프로파일링 시작 (30초)..."
	@APP_PID=$$(docker inspect --format '{{.State.Pid}}' nebula-ai 2>/dev/null || echo ""); \
	if [ -z "$$APP_PID" ]; then \
		echo "❌ nebula-ai 컨테이너가 실행 중이지 않습니다. 'make start' 먼저 실행하세요."; \
		exit 1; \
	fi; \
	docker-compose --profile profiling run --rm profiler bash -c " \
		pip install py-spy > /dev/null 2>&1 && \
		echo '🔍 프로파일링 시작 (PID: $$APP_PID)...' && \
		py-spy record -o /profiles/baseline_\$$(date +%s).svg --pid $$APP_PID -d 30 && \
		echo '✅ 프로파일링 완료! profiles/ 디렉토리 확인하세요.' \
	"

# 빠른 프로파일링 (10초)
.PHONY: profile-quick
profile-quick: profile-setup
	@echo "⚡ 빠른 프로파일링 시작 (10초)..."
	@APP_PID=$$(docker inspect --format '{{.State.Pid}}' nebula-ai 2>/dev/null || echo ""); \
	if [ -z "$$APP_PID" ]; then \
		echo "❌ nebula-ai 컨테이너가 실행 중이지 않습니다."; \
		exit 1; \
	fi; \
	docker-compose --profile profiling run --rm profiler bash -c " \
		pip install py-spy > /dev/null 2>&1 && \
		py-spy record -o /profiles/quick_\$$(date +%s).svg --pid $$APP_PID -d 10 \
	"

# 부하 테스트와 함께 프로파일링
.PHONY: profile-load
profile-load: profile-setup
	@echo "🚀 부하 테스트와 함께 프로파일링..."
	@APP_PID=$$(docker inspect --format '{{.State.Pid}}' nebula-ai 2>/dev/null || echo ""); \
	if [ -z "$$APP_PID" ]; then \
		echo "❌ nebula-ai 컨테이너가 실행 중이지 않습니다."; \
		exit 1; \
	fi; \
	echo "🔍 백그라운드에서 프로파일링 시작..."; \
	docker-compose --profile profiling run --rm profiler bash -c " \
		pip install py-spy > /dev/null 2>&1 && \
		py-spy record -o /profiles/load_test_\$$(date +%s).svg --pid $$APP_PID -d 60 \
	" & \
	echo "⏳ 5초 대기 후 부하 테스트 시작..."; \
	sleep 5; \
	echo "🚀 API 부하 테스트 실행 (100회 요청)..."; \
	for i in $$(seq 1 100); do \
		curl -s http://localhost:8000/ > /dev/null & \
		if [ $$((i % 10)) -eq 0 ]; then echo "진행: $$i/100"; fi; \
	done; \
	wait; \
	echo "✅ 부하 테스트 완료! 프로파일링 결과를 기다리는 중..."

# 상세 프로파일링 (speedscope 형식)
.PHONY: profile-detailed
profile-detailed: profile-setup
	@echo "📊 상세 프로파일링 시작 (speedscope 형식)..."
	@APP_PID=$$(docker inspect --format '{{.State.Pid}}' nebula-ai 2>/dev/null || echo ""); \
	if [ -z "$$APP_PID" ]; then \
		echo "❌ nebula-ai 컨테이너가 실행 중이지 않습니다."; \
		exit 1; \
	fi; \
	docker-compose --profile profiling run --rm profiler bash -c " \
		pip install py-spy > /dev/null 2>&1 && \
		py-spy record -f speedscope -o /profiles/detailed/detailed_\$$(date +%s).json --pid $$APP_PID -d 45 \
	"

# 실시간 프로파일링 (top 형식)
.PHONY: profile-top
profile-top:
	@echo "📊 실시간 성능 모니터링 (Ctrl+C로 종료)..."
	@APP_PID=$$(docker inspect --format '{{.State.Pid}}' nebula-ai 2>/dev/null || echo ""); \
	if [ -z "$$APP_PID" ]; then \
		echo "❌ nebula-ai 컨테이너가 실행 중이지 않습니다."; \
		exit 1; \
	fi; \
	docker-compose --profile profiling run --rm profiler bash -c " \
		pip install py-spy > /dev/null 2>&1 && \
		py-spy top --pid $$APP_PID \
	"

# GIL 경합 프로파일링
.PHONY: profile-gil
profile-gil: profile-setup
	@echo "🔒 GIL 경합 프로파일링..."
	@APP_PID=$$(docker inspect --format '{{.State.Pid}}' nebula-ai 2>/dev/null || echo ""); \
	if [ -z "$$APP_PID" ]; then \
		echo "❌ nebula-ai 컨테이너가 실행 중이지 않습니다."; \
		exit 1; \
	fi; \
	docker-compose --profile profiling run --rm profiler bash -c " \
		pip install py-spy > /dev/null 2>&1 && \
		py-spy record --gil -o /profiles/gil_contention_\$$(date +%s).svg --pid $$APP_PID -d 30 \
	"

# 특정 API 엔드포인트 프로파일링
.PHONY: profile-api
profile-api: profile-setup
	@if [ -z "$(ENDPOINT)" ]; then \
		echo "❌ 사용법: make profile-api ENDPOINT=/path/to/api"; \
		echo "예시: make profile-api ENDPOINT=/chat/stream"; \
		exit 1; \
	fi
	@echo "🎯 API 엔드포인트 프로파일링: $(ENDPOINT)"
	@APP_PID=$$(docker inspect --format '{{.State.Pid}}' nebula-ai 2>/dev/null || echo ""); \
	if [ -z "$$APP_PID" ]; then \
		echo "❌ nebula-ai 컨테이너가 실행 중이지 않습니다."; \
		exit 1; \
	fi; \
	echo "🔍 백그라운드에서 프로파일링 시작..."; \
	docker-compose --profile profiling run --rm profiler bash -c " \
		pip install py-spy > /dev/null 2>&1 && \
		py-spy record -o /profiles/api_$$(echo '$(ENDPOINT)' | sed 's/[^a-zA-Z0-9]/_/g')_\$$(date +%s).svg --pid $$APP_PID -d 30 \
	" & \
	sleep 3; \
	echo "🚀 API 요청 실행: $(ENDPOINT)"; \
	for i in $$(seq 1 20); do \
		curl -s http://localhost:8000$(ENDPOINT) > /dev/null & \
	done; \
	wait

# 프로파일 결과 열기 (macOS)
.PHONY: profile-open
profile-open:
	@echo "📊 최신 프로파일 결과 열기..."
	@LATEST_SVG=$$(ls -t profiles/*.svg 2>/dev/null | head -1); \
	if [ -n "$$LATEST_SVG" ]; then \
		echo "📂 열기: $$LATEST_SVG"; \
		open "$$LATEST_SVG"; \
	else \
		echo "❌ 프로파일 결과가 없습니다. 먼저 프로파일링을 실행하세요."; \
	fi

# 프로파일 결과 목록
.PHONY: profile-list
profile-list:
	@echo "📋 프로파일 결과 목록:"
	@if [ -d profiles ] && [ -n "$$(ls profiles/*.svg 2>/dev/null)" ]; then \
		ls -lah profiles/*.svg | while read line; do \
			echo "  $$line"; \
		done; \
		echo ""; \
		echo "💡 브라우저로 열기: make profile-open"; \
	else \
		echo "  📭 프로파일 결과가 없습니다."; \
		echo "  🚀 프로파일링 시작: make profile"; \
	fi

# 프로파일 결과 정리
.PHONY: profile-clean
profile-clean:
	@echo "🧹 프로파일 결과 정리..."
	@if [ -d profiles ]; then \
		find profiles -name "*.svg" -o -name "*.json" | wc -l | xargs echo "삭제할 파일 수:"; \
		rm -rf profiles/*.svg profiles/*.json profiles/*/*.svg profiles/*/*.json 2>/dev/null || true; \
		echo "✅ 정리 완료"; \
	else \
		echo "📭 정리할 파일이 없습니다."; \
	fi

# 프로파일링 도움말
.PHONY: profile-help
profile-help:
	@echo "🔍 성능 프로파일링 명령어 가이드"
	@echo "==============================="
	@echo ""
	@echo "📊 기본 프로파일링:"
	@echo "  profile          : 기본 프로파일링 (30초)"
	@echo "  profile-quick    : 빠른 프로파일링 (10초)"
	@echo "  profile-top      : 실시간 성능 모니터링"
	@echo ""
	@echo "🚀 고급 프로파일링:"
	@echo "  profile-load     : 부하 테스트와 함께 프로파일링"
	@echo "  profile-detailed : 상세 프로파일링 (speedscope 형식)"
	@echo "  profile-gil      : GIL 경합 분석"
	@echo "  profile-api ENDPOINT=/path : 특정 API 프로파일링"
	@echo ""
	@echo "📁 결과 관리:"
	@echo "  profile-list     : 프로파일 결과 목록"
	@echo "  profile-open     : 최신 결과 브라우저에서 열기"
	@echo "  profile-clean    : 프로파일 결과 정리"
	@echo ""
	@echo "💡 사용 예시:"
	@echo "  make profile                        # 기본 프로파일링"
	@echo "  make profile-api ENDPOINT=/chat     # 채팅 API 프로파일링"
	@echo "  make profile-load                   # 부하 테스트 프로파일링"
	@echo ""
	@echo "📂 결과 위치: profiles/ 디렉토리"
	@echo "🌐 시각화: SVG 파일을 브라우저에서 열어 flamegraph 확인"

# ============================================================================
# 📊 모니터링 명령어
# ============================================================================

.PHONY: monitoring
monitoring: monitoring-stop monitoring-start

.PHONY: monitoring-start
monitoring-start:
	@echo "📊 모니터링 시스템 시작..."
	docker-compose -f docker-compose.monitoring.yml up -d
	@echo "✅ 모니터링 시스템이 시작되었습니다!"
	@echo "🔍 프로메테우스: http://localhost:9090"
	@echo "📈 그라파나: http://localhost:3000 (admin/nebula2024!)"

.PHONY: monitoring-stop
monitoring-stop:
	@echo "🛑 모니터링 시스템 중지..."
	docker-compose -f docker-compose.monitoring.yml down

.PHONY: monitoring-restart
monitoring-restart: monitoring-stop monitoring-start

.PHONY: monitoring-logs
monitoring-logs:
	@echo "📋 모니터링 시스템 로그 확인..."
	docker-compose -f docker-compose.monitoring.yml logs -f

.PHONY: monitoring-logs-prometheus
monitoring-logs-prometheus:
	@echo "📋 프로메테우스 로그 확인..."
	docker-compose -f docker-compose.monitoring.yml logs -f prometheus

.PHONY: monitoring-logs-grafana
monitoring-logs-grafana:
	@echo "📋 그라파나 로그 확인..."
	docker-compose -f docker-compose.monitoring.yml logs -f grafana

.PHONY: monitoring-status
monitoring-status:
	@echo "📊 모니터링 서비스 상태..."
	docker-compose -f docker-compose.monitoring.yml ps

.PHONY: monitoring-clean
monitoring-clean:
	@echo "🧹 모니터링 시스템 정리 (볼륨 포함)..."
	docker-compose -f docker-compose.monitoring.yml down --volumes

.PHONY: monitoring-reset
monitoring-reset: monitoring-clean monitoring-start
	@echo "♻️  모니터링 시스템 완전 초기화 완료!"

.PHONY: metrics-check
metrics-check:
	@echo "🔍 애플리케이션 메트릭 확인..."
	@if curl -s http://localhost:8000/metrics > /dev/null 2>&1; then \
		echo "✅ 메트릭 엔드포인트 정상 작동"; \
		echo "📊 메트릭 수: $$(curl -s http://localhost:8000/metrics | grep -c '^[a-zA-Z]')"; \
	else \
		echo "❌ 메트릭 엔드포인트 접근 실패"; \
	fi

.PHONY: prometheus-reload
prometheus-reload:
	@echo "🔄 프로메테우스 설정 리로드..."
	curl -X POST http://localhost:9090/-/reload

# ============================================================================
# 🧹 정리 및 유지보수 명령어
# ============================================================================

.PHONY: clean
clean:
	@echo "🧹 개발 환경 정리 (컨테이너, 이미지, 볼륨)..."
	docker-compose down --volumes --rmi all
	docker system prune -f

.PHONY: clean-cov
clean-cov:
	rm -rf .coverage htmlcov coverage.xml

.PHONY: clean-test
clean-test: test-env-stop
	docker system prune -f

.PHONY: reset
reset: clean fix-buildx build start
	@echo "♻️  개발 환경 완전 초기화 완료!"

.PHONY: fix-buildx
fix-buildx:
	@echo "🔧 Docker buildx 환경 정리..."
	@docker buildx ls | grep -q "multiarch-builder" && docker buildx rm multiarch-builder || true
	@docker container prune -f >/dev/null 2>&1 || true

.PHONY: fix
fix:
	@echo "🛠️  개발 환경 문제 해결..."
	@echo "1. Docker buildx 정리..."
	@make fix-buildx
	@echo "2. 사용하지 않는 컨테이너 정리..."
	@docker container prune -f
	@echo "3. 사용하지 않는 이미지 정리..."
	@docker image prune -f
	@echo "4. 네트워크 정리..."
	@docker network prune -f
	@echo "✅ 문제 해결 완료!"

# ============================================================================
# 🚀 통합 명령어
# ============================================================================

.PHONY: full-start
full-start: start monitoring-start
	@echo "🚀 전체 시스템 (애플리케이션 + 모니터링) 시작 완료!"
	@echo ""
	@echo "📱 애플리케이션 서비스:"
	@echo "   - 메인 API: http://localhost:8001"
	@echo "   - 헬스체크: http://localhost:8001/health"
	@echo "   - API 문서: http://localhost:8001/docs"
	@echo "   - 메트릭: http://localhost:8001/metrics"
	@echo ""
	@echo "📊 모니터링 서비스:"
	@echo "   - 프로메테우스: http://localhost:9090"
	@echo "   - 그라파나: http://localhost:3000 (admin/nebula2024!)"
	@echo "   - 노드 익스포터: http://localhost:9100"
	@echo ""
	@echo "🎯 빠른 시작 가이드:"
	@echo "   1. 그라파나에 로그인하여 'Nebula AI' 대시보드 확인"
	@echo "   2. 프로메테우스에서 메트릭 수집 상태 확인"
	@echo "   3. API 호출 후 메트릭 변화 관찰"

.PHONY: stop-all
stop-all: stop monitoring-stop
	@echo "🛑 모든 서비스 중지 완료"

# ============================================================================
# 📚 도움말 명령어
# ============================================================================

.PHONY: help
help:
	@echo "🚀 Nebula AI - Makefile 명령어 가이드"
	@echo "====================================="
	@echo ""
	@echo "📦 기본 개발 명령어:"
	@echo "  dev              : 테스트 + 개발 환경 시작 (권장)"
	@echo "  dev-quick        : 빠른 개발 환경 시작 (캐시 사용)"
	@echo "  dev-no-test      : 테스트 없이 개발 환경 시작"
	@echo "  run-local        : 로컬에서 FastAPI 서버 실행"
	@echo ""
	@echo "🏗️ 환경 관리:"
	@echo "  start            : Docker 서비스 시작"
	@echo "  stop             : Docker 서비스 중지"
	@echo "  restart          : Docker 서비스 재시작"
	@echo "  build            : Docker 이미지 빌드 (캐시 무시)"
	@echo "  build-quick      : Docker 이미지 빠른 빌드 (캐시 사용)"
	@echo "  status           : 서비스 상태 확인"
	@echo "  logs             : 모든 서비스 로그"
	@echo "  shell            : 웹 컨테이너 쉘 접속"
	@echo ""
	@echo "🧪 테스트:"
	@echo "  test             : 기본 테스트 실행"
	@echo "  test-all         : 모든 테스트 실행"
	@echo "  test-cov         : 커버리지 포함 테스트"
	@echo "  test-cov-html    : 커버리지 HTML 리포트"
	@echo ""
	@echo "🔴 Redis 관리:"
	@echo "  redis-ping       : Redis 연결 테스트"
	@echo "  redis-restart    : Redis 재시작"
	@echo "  redis-info       : Redis 정보 확인"
	@echo ""
	@echo "📊 모니터링:"
	@echo "  monitoring-start : 모니터링 시스템 시작"
	@echo "  monitoring-stop  : 모니터링 시스템 중지"
	@echo "  metrics-check    : 메트릭 확인"
	@echo ""
	@echo "🔍 성능 프로파일링:"
	@echo "  profile          : 기본 프로파일링 (30초)"
	@echo "  profile-quick    : 빠른 프로파일링 (10초)"
	@echo "  profile-load     : 부하 테스트 프로파일링"
	@echo "  profile-top      : 실시간 성능 모니터링"
	@echo "  profile-help     : 프로파일링 상세 가이드"
	@echo ""
	@echo "🚀 통합 명령어:"
	@echo "  full-start       : 전체 시스템 시작"
	@echo "  stop-all         : 모든 서비스 중지"
	@echo ""
	@echo "🧹 정리/문제해결:"
	@echo "  clean            : 환경 정리"
	@echo "  reset            : 환경 완전 초기화"
	@echo "  fix              : 문제 해결"
	@echo ""
	@echo "💡 빠른 시작: 'make dev' → http://localhost:8001"
	@echo "🆘 문제 발생 시: 'make fix' → 'make dev'"

# ============================================================================
# 🔧 하위 호환성 (기존 명령어 지원)
# ============================================================================

# 기존 명령어들을 새로운 명령어로 매핑
.PHONY: local
local: dev

.PHONY: local-no-test
local-no-test: dev-no-test

.PHONY: run
run: run-local

.PHONY: dev-start
dev-start: start

.PHONY: dev-stop
dev-stop: stop

.PHONY: dev-build
dev-build: build

.PHONY: dev-build-quick
dev-build-quick: build-quick

.PHONY: dev-rebuild
dev-rebuild: reset

.PHONY: dev-restart
dev-restart: restart

.PHONY: dev-logs
dev-logs: logs

.PHONY: dev-logs-web
dev-logs-web: logs-web

.PHONY: dev-logs-celery
dev-logs-celery: logs-celery

.PHONY: dev-status
dev-status: status

.PHONY: dev-shell
dev-shell: shell

.PHONY: dev-shell-celery
dev-shell-celery: shell-celery

.PHONY: dev-clean
dev-clean: clean

.PHONY: dev-reset
dev-reset: reset

.PHONY: dev-fix
dev-fix: fix

.PHONY: dev-fix-buildx
dev-fix-buildx: fix-buildx

.PHONY: fix-whitespace
fix-whitespace: format

.PHONY: test-setup
test-setup: test-env-start

.PHONY: test-clean
test-clean: test-env-stop

.PHONY: test-services
test-services: test-env-status

.PHONY: test-logs
test-logs: test-env-logs

.PHONY: cov-html
cov-html: test-cov-html

.PHONY: full-monitoring
full-monitoring: full-start

.PHONY: test-help
test-help:
	@echo "🔖 북마크 저장 시스템 테스트 명령어"
	@echo "=================================="
	@echo "test-all        : 모든 테스트 실행"
	@echo "test-unit       : 단위 테스트만 실행"
	@echo "test-manual     : 수동 테스트만 실행"
	@echo "test-performance: 성능 테스트만 실행"
	@echo "test-env-start  : 테스트 환경 설정"
	@echo "test-env-stop   : 테스트 환경 정리"
	@echo "test-env-status : 테스트 서비스 상태 확인"
	@echo "test-env-logs   : 테스트 서비스 로그 확인"
	@echo ""
	@echo "📚 자세한 가이드: docs/testing/TESTING_GUIDE.md"

.PHONY: dev-help
dev-help:
	@echo "🛠️  개발 환경 명령어는 기본 명령어로 통합되었습니다."
	@echo "📚 전체 명령어 가이드: make help"