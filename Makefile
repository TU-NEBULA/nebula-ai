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