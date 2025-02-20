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

    class Config:
        env_file = ".env"

settings = Settings()
    
