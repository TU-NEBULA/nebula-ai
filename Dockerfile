FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir "numpy<2"
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY .env /app/.env

EXPOSE 8000

CMD ["python", "app.py"]
