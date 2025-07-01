# ============================================================================
# Nebula AI - Makefile
# ============================================================================

# ============================================================================
# 📦 기본 개발 명령어 (가장 자주 사용)
# ============================================================================

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