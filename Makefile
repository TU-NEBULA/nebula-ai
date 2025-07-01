.PHONY: freeze
freeze:
	pipenv requirements > requirements.txt

.PHONY: install
install:
	pipenv install --dev

.PHONY: local
local: test stop build start

.PHONY: local-no-test
local-no-test: stop build start

.PHONY: run
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

.PHONY: start
start:
	docker-compose up -d

.PHONY: stop
stop: 
	docker-compose down

.PHONY: build
build:
	docker-compose build

.PHONY: restart
restart: stop build start

# 개발 환경 관련 명령어들
.PHONY: dev
dev: test dev-stop dev-build dev-start

.PHONY: dev-no-test
dev-no-test: dev-stop dev-build dev-start

.PHONY: dev-start
dev-start:
	@echo "🚀 개발 환경 시작..."
	docker-compose -f docker-compose.dev.yml up -d

.PHONY: dev-stop
dev-stop:
	@echo "🛑 개발 환경 중지..."
	docker-compose -f docker-compose.dev.yml down

.PHONY: dev-build
dev-build: dev-fix-buildx
	@echo "🔨 개발 환경 이미지 빌드..."
	docker-compose -f docker-compose.dev.yml build --no-cache

.PHONY: dev-build-quick
dev-build-quick: dev-fix-buildx  
	@echo "⚡ 개발 환경 빠른 빌드 (캐시 사용)..."
	DOCKER_BUILDKIT=1 docker-compose -f docker-compose.dev.yml build

.PHONY: dev-build-cache
dev-build-cache: dev-fix-buildx
	@echo "🏎️ 최적화된 캐시 빌드..."
	DOCKER_BUILDKIT=1 docker build --target production --cache-from nebula-ai:latest -t nebula-ai:latest .

.PHONY: dev-fix-buildx
dev-fix-buildx:
	@echo "🔧 Docker buildx 환경 정리..."
	@docker buildx ls | grep -q "multiarch-builder" && docker buildx rm multiarch-builder || true
	@docker container prune -f >/dev/null 2>&1 || true

.PHONY: dev-rebuild
dev-rebuild: dev-fix-buildx
	@echo "🔄 개발 환경 전체 재빌드..."
	docker-compose -f docker-compose.dev.yml down --volumes
	docker-compose -f docker-compose.dev.yml build --no-cache
	docker-compose -f docker-compose.dev.yml up -d

.PHONY: dev-restart
dev-restart: dev-stop dev-build-quick dev-start

.PHONY: dev-quick
dev-quick: dev-stop dev-build-quick dev-start

.PHONY: dev-logs
dev-logs:
	@echo "📋 개발 환경 로그 확인..."
	docker-compose -f docker-compose.dev.yml logs -f

.PHONY: dev-logs-web
dev-logs-web:
	@echo "📋 웹 서비스 로그 확인..."
	docker-compose -f docker-compose.dev.yml logs -f web

.PHONY: dev-logs-celery
dev-logs-celery:
	@echo "📋 Celery 워커 로그 확인..."
	docker-compose -f docker-compose.dev.yml logs -f celery_worker

.PHONY: dev-status
dev-status:
	@echo "📊 개발 환경 서비스 상태..."
	docker-compose -f docker-compose.dev.yml ps

.PHONY: dev-shell
dev-shell:
	@echo "💻 웹 컨테이너 쉘 접속..."
	docker-compose -f docker-compose.dev.yml exec web bash

.PHONY: dev-shell-celery
dev-shell-celery:
	@echo "💻 Celery 컨테이너 쉘 접속..."
	docker-compose -f docker-compose.dev.yml exec celery_worker bash

.PHONY: dev-clean
dev-clean:
	@echo "🧹 개발 환경 정리 (컨테이너, 이미지, 볼륨)..."
	docker-compose -f docker-compose.dev.yml down --volumes --rmi all
	docker system prune -f

.PHONY: dev-reset
dev-reset: dev-clean dev-fix-buildx dev-build dev-start
	@echo "♻️  개발 환경 완전 초기화 완료!"

.PHONY: dev-fix
dev-fix:
	@echo "🛠️  개발 환경 문제 해결..."
	@echo "1. Docker buildx 정리..."
	@make dev-fix-buildx
	@echo "2. 사용하지 않는 컨테이너 정리..."
	@docker container prune -f
	@echo "3. 사용하지 않는 이미지 정리..."
	@docker image prune -f
	@echo "4. 네트워크 정리..."
	@docker network prune -f
	@echo "✅ 문제 해결 완료!"

# Redis 관리 명령어들 (로컬 컨테이너)
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

.PHONY: redis-benchmark
redis-benchmark:
	@echo "🏃‍♂️ Redis 성능 벤치마크 실행..."
	docker exec nebula-redis-dev redis-benchmark -a dev_password_123 -t set,get -n 10000 -q

.PHONY: redis-logs
redis-logs:
	@echo "📋 Redis 로그 확인..."
	docker-compose -f docker-compose.dev.yml logs -f redis

.PHONY: redis-restart
redis-restart:
	@echo "🔄 Redis 재시작..."
	docker-compose -f docker-compose.dev.yml restart redis

.PHONY: redis-start
redis-start:
	@echo "🚀 Redis 시작..."
	docker-compose -f docker-compose.dev.yml up -d redis

.PHONY: redis-stop
redis-stop:
	@echo "🛑 Redis 중지..."
	docker-compose -f docker-compose.dev.yml stop redis

.PHONY: dev-help
dev-help:
	@echo "🛠️  개발 환경 명령어 도움말"
	@echo "=========================="
	@echo "📦 환경 관리:"
	@echo "  dev             : 테스트 + 개발 환경 전체 재시작"
	@echo "  dev-no-test     : 테스트 없이 개발 환경 재시작"
	@echo "  dev-quick       : 빠른 재시작 (캐시 사용)"
	@echo "  dev-start       : 개발 환경 시작"
	@echo "  dev-stop        : 개발 환경 중지"
	@echo "  dev-build       : 개발 환경 이미지 빌드 (캐시 무시)"
	@echo "  dev-build-quick : 개발 환경 빠른 빌드 (캐시 사용)"
	@echo "  dev-rebuild     : 전체 재빌드 (캐시 무시)"
	@echo "  dev-restart     : 개발 환경 재시작"
	@echo ""
	@echo "📋 로그 및 상태:"
	@echo "  dev-logs        : 모든 서비스 로그 실시간 확인"
	@echo "  dev-logs-web    : 웹 서비스 로그만 확인"
	@echo "  dev-logs-celery : Celery 워커 로그만 확인"
	@echo "  dev-status      : 서비스 상태 확인"
	@echo ""
	@echo "💻 접속 및 쉘:"
	@echo "  dev-shell       : 웹 컨테이너 쉘 접속"
	@echo "  dev-shell-celery: Celery 컨테이너 쉘 접속"
	@echo ""
	@echo "🔴 Redis 관리 (로컬 컨테이너):"
	@echo "  redis-start     : Redis 시작"
	@echo "  redis-stop      : Redis 중지"
	@echo "  redis-restart   : Redis 재시작"
	@echo "  redis-ping      : Redis 연결 테스트"
	@echo "  redis-info      : Redis 정보 확인"
	@echo "  redis-memory    : Redis 메모리 사용량"
	@echo "  redis-clients   : Redis 클라이언트 연결 상태"
	@echo "  redis-slowlog   : Redis 슬로우 로그"
	@echo "  redis-keys      : Redis 키 목록"
	@echo "  redis-celery-keys: Celery 관련 키"
	@echo "  redis-benchmark : Redis 성능 테스트"
	@echo "  redis-logs      : Redis 로그 확인"
	@echo "  redis-flush-dev : Redis 데이터 삭제 (주의!)"
	@echo ""
	@echo "🧹 정리 및 문제 해결:"
	@echo "  dev-clean       : 모든 컨테이너/이미지/볼륨 삭제"
	@echo "  dev-reset       : 개발 환경 완전 초기화"
	@echo "  dev-fix         : 개발 환경 문제 해결 (buildx, 정리)"
	@echo ""
	@echo "💡 개발 시작: 'make dev' 실행 후 http://localhost:8000 접속"
	@echo "📝 코드 변경 시 자동으로 컨테이너에 반영됩니다"
	@echo "🚀 빠른 재시작: 'make dev-quick' 사용"
	@echo "🔴 Redis 연결 문제 시: 'make redis-ping' 또는 'make redis-restart'"
	@echo "🛠️  문제 발생 시: 'make dev-fix' 실행"

.PHONY: test
test:
	pytest tests --disable-warnings -v

.PHONY: test-cov 
test-cov:
	pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-report=html \
		tests

.PHONY: cov-html
cov-html: test-cov
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open htmlcov/index.html; \
	elif command -v open >/dev/null 2>&1; then \
		open htmlcov/index.html; \
	else \
		echo "htmlcov/index.html 을 브라우저로 열어 확인하세요."; \
	fi

.PHONY: clean-cov
clean-cov:
	rm -rf .coverage htmlcov coverage.xml

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

fix-whitespace:
	@echo "=== Trailing whitespace 제거 ==="
	@find $(FASTAPI_SRC) -type f -name '*.py' \
	  -exec sed -i 's/[[:blank:]]\+$$//' {} +

# 테스트 관련 명령어들
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

.PHONY: test-setup
test-setup:
	@echo "🚀 테스트 환경 설정..."
	docker-compose -f docker/test/docker-compose.test.yml up -d
	@echo "⏳ 서비스 준비 대기 중..."
	sleep 10
	python scripts/test/setup_dev_environment.py

.PHONY: test-clean
test-clean:
	@echo "🧹 테스트 환경 정리..."
	docker-compose -f docker/test/docker-compose.test.yml down
	docker system prune -f

.PHONY: test-services
test-services:
	@echo "📊 테스트 서비스 상태 확인..."
	docker-compose -f docker/test/docker-compose.test.yml ps

.PHONY: test-logs
test-logs:
	@echo "📋 테스트 서비스 로그 확인..."
	docker-compose -f docker/test/docker-compose.test.yml logs

.PHONY: test-help
test-help:
	@echo "🔖 북마크 저장 시스템 테스트 명령어"
	@echo "=================================="
	@echo "test-all        : 모든 테스트 실행"
	@echo "test-unit       : 단위 테스트만 실행"
	@echo "test-manual     : 수동 테스트만 실행"
	@echo "test-performance: 성능 테스트만 실행"
	@echo "test-setup      : 테스트 환경 설정"
	@echo "test-clean      : 테스트 환경 정리"
	@echo "test-services   : 테스트 서비스 상태 확인"
	@echo "test-logs       : 테스트 서비스 로그 확인"
	@echo ""
	@echo "📚 자세한 가이드: docs/testing/TESTING_GUIDE.md"

# 모니터링 관련 명령어들
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

.PHONY: full-monitoring
full-monitoring: dev-start monitoring-start
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
stop-all: dev-stop monitoring-stop
	@echo "🛑 모든 서비스 중지 완료"