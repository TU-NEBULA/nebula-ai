FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip pipenv

RUN pipenv --python /usr/local/bin/python3.11

COPY Pipfile Pipfile.lock ./

RUN pipenv install --deploy --ignore-pipfile

COPY . .

COPY .env /app/.env

EXPOSE 8000

CMD ["pipenv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
