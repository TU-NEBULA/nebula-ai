FROM python:3.12-bullseye

WORKDIR /app

# Setup apt properly with GPG keys
RUN apt-get update && \
    apt-get install -y --no-install-recommends gnupg2 dirmngr apt-transport-https ca-certificates && \
    apt-key update && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libffi-dev \
    openjdk-17-jre-headless \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install SQLite 3.45.3 or higher
RUN wget https://www.sqlite.org/2024/sqlite-autoconf-3450300.tar.gz && \
    tar xvfz sqlite-autoconf-3450300.tar.gz && \
    cd sqlite-autoconf-3450300 && \
    ./configure && \
    make && \
    make install && \
    cd .. && \
    rm -rf sqlite-autoconf-3450300*

# Python이 새로 설치한 SQLite를 사용하도록 설정
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Python 재설치 (새 SQLite를 사용하도록)
RUN cd /tmp && \
    wget https://www.python.org/ftp/python/3.12.0/Python-3.12.0.tgz && \
    tar xzf Python-3.12.0.tgz && \
    cd Python-3.12.0 && \
    ./configure --enable-optimizations && \
    make -j $(nproc) && \
    make altinstall && \
    cd .. && \
    rm -rf Python-3.12.0*

RUN pip install --no-cache-dir --upgrade pip pipenv

RUN pipenv --python /usr/local/bin/python3.12

COPY Pipfile Pipfile.lock ./

RUN pipenv install --deploy --ignore-pipfile

RUN pipenv run python -m nltk.downloader stopwords

COPY . .

COPY .env /app/.env

# 로그 디렉토리 생성
RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["pipenv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
