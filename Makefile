.PHONY: freeze
freeze:
	pipenv requirements > requirements.txt

.PHONY: install
install:
	pipenv install --dev

.PHONY: local
local: stop build start

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
	docker-compose build --no-cache

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
