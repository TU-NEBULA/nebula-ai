FROM python:slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libffi-dev \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip pipenv

RUN pipenv --python /usr/local/bin/python3.13

COPY Pipfile Pipfile.lock ./

RUN pipenv install --deploy --ignore-pipfile

RUN pipenv run python -m nltk.downloader stopwords

COPY . .

COPY .env /app/.env

EXPOSE 8000

CMD ["pipenv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
