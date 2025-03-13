import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()
class Settings(BaseSettings):
    HUGGINGFACEHUB_API_TOKEN: str
    MODEL_NAME: str
    CACHE_DIR: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_KEY_ID: str
    REGION: str
    BUCKET_NAME: str
    CHROMA_DB_URI: str
    RABBITMQ_HOST: str
    RABBITMQ_QUEUE: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str

    class Config:
        env_file = ".env"

settings = Settings()
    
