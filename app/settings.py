from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    DATABASE_URL: str  # required environment variable

    JWT_SECRET: str  # required environment variable
    JWT_ALGORITHM: str = "HS256"  # optional environement variable with default value
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
