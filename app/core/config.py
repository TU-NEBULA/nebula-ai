import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(override=True)
class Settings(BaseSettings):
    HUGGINGFACEHUB_API_TOKEN: str
    EMBEDDING_MODEL_NAME: str
    MODEL_NAME: str
    CACHE_DIR: str
    OPENAI_API_KEY: str
    OPENAI_EMBED_MODEL: str
    OPENAI_MODEL: str
    LANGSMITH_TRACING: bool
    LANGSMITH_ENDPOINT: str
    LANGSMITH_API_KEY: str
    LANGSMITH_PROJECT: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_KEY_ID: str
    REGION: str
    BUCKET_NAME: str
    CHROMA_DB_URI: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USERNAME: str
    RABBITMQ_PASSWORD: str
    EXTRACT_REQ_QUEUE: str
    CHAT_REQ_QUEUE: str
    BASE_THUMBNAIL: str

    @property
    def RABBITMQ_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USERNAME}:{self.RABBITMQ_PASSWORD}" \
               f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"


    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
    
