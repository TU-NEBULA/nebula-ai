.PHONY: freeze
freeze:
	pipenv requirements > requirements.txt

.PHONY: run
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

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
