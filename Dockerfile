# =====================================
# Stage 1: Base Dependencies
# =====================================
FROM python:3.12-alpine AS base

# 기본 시스템 패키지 (빌드 도구 제외)
RUN apk add --no-cache \
    openjdk17 \
    sqlite \
    postgresql17-dev \
    && rm -rf /var/cache/apk/*

# Java 환경 변수
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk
ENV PATH="$JAVA_HOME/bin:$PATH"
ENV LD_LIBRARY_PATH="$JAVA_HOME/lib/server:$JAVA_HOME/lib:$LD_LIBRARY_PATH"

# =====================================
# Stage 2: Build Dependencies
# =====================================
FROM base AS builder

# 빌드 도구들 (임시로만 설치)
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    rust \
    cargo

# pip 업그레이드 및 pipenv 설치
RUN pip install --no-cache-dir --upgrade pip pipenv

WORKDIR /app

# pipenv Python 버전 설정
RUN pipenv --python /usr/local/bin/python

# 의존성 파일만 먼저 복사 (캐시 최적화)
COPY Pipfile Pipfile.lock ./

# 의존성 설치 (캐시될 가능성이 높은 레이어)
RUN pipenv install --deploy --ignore-pipfile

# NLTK 데이터 다운로드
RUN pipenv run python -m nltk.downloader stopwords

# =====================================
# Stage 3: Production
# =====================================
FROM base AS production

# 작업 디렉토리 설정
WORKDIR /app

# pip 설치 (builder에서 설치한 pipenv는 가져오지 않음)
RUN pip install --no-cache-dir --upgrade pip pipenv

# pipenv Python 버전 설정
RUN pipenv --python /usr/local/bin/python

# builder 스테이지에서 가상환경 복사
COPY --from=builder /root/.local/share/virtualenvs /root/.local/share/virtualenvs

# Pipfile도 복사 (pipenv가 올바른 가상환경을 찾을 수 있도록)
COPY --from=builder /app/Pipfile /app/Pipfile.lock ./

# 애플리케이션 코드 복사 (가장 마지막에)
COPY app/ ./app/

# 환경 변수 파일 복사
COPY .env /app/.env

# 로그 디렉토리 생성
RUN mkdir -p /app/logs

# 포트 노출
EXPOSE 8000

# 애플리케이션 실행
CMD ["pipenv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
