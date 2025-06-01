"""
애플리케이션 구성 설정 모듈

이 모듈은 환경 변수, API 키, 서비스 URL 등 애플리케이션 구성에 필요한 설정을 관리합니다.
Pydantic을 사용하여 환경 변수를 검증하고 타입을 보장합니다.
"""
import os
from dotenv import load_dotenv
from pydantic import computed_field, Field
from pydantic_settings import BaseSettings

load_dotenv(override=True)

class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    
    환경 변수를 통해 설정되는 모든 구성 요소를 정의합니다.
    .env 파일 또는 환경 변수에서 값을 로드합니다.
    """
    # 환경 설정
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    HUGGINGFACEHUB_API_TOKEN: str
    EMBEDDING_MODEL_NAME: str
    MODEL_NAME: str
    CACHE_DIR: str
    OPENAI_API_KEY: str
    OPENAI_EMBED_MODEL: str
    OPENAI_MODEL: str
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_TIMEOUT: float = 30.0
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
    REDIS_URL: str
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USERNAME: str
    RABBITMQ_PASSWORD: str
    EXTRACT_REQ_QUEUE: str
    CHAT_REQ_QUEUE: str
    BOOKMARK_SAVE_QUEUE: str
    BASE_THUMBNAIL: str
    
    # PostgreSQL RDS 설정
    POSTGRES_HOST: str = Field(..., description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_USER: str = Field(..., description="PostgreSQL user")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL password")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")
    
    # 데이터베이스 연결 풀 설정
    DB_POOL_SIZE: int = Field(default=20)
    DB_MAX_OVERFLOW: int = Field(default=0)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=3600)
    
    # SSL 설정 (RDS에서 권장)
    DB_SSL_MODE: str = Field(default="require")

    @property
    def RABBITMQ_URL(self) -> str:
        """
        RabbitMQ 연결 URL을 생성합니다.
        
        Returns:
            str: RabbitMQ 연결을 위한 AMQP URL 문자열
        """
        return f"amqp://{self.RABBITMQ_USERNAME}:{self.RABBITMQ_PASSWORD}" \
               f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """동기 데이터베이스 URL (Alembic용)"""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?sslmode={self.DB_SSL_MODE}"
        )
    
    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """비동기 데이터베이스 URL (SQLModel용)"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?ssl={self.DB_SSL_MODE}"
        )

    class Config:
        """
        Pydantic 구성 클래스
        
        환경 변수 파일 위치와 인코딩을 지정합니다.
        """
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
    
