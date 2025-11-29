from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    example_secret: str = "example secret value"

    DATABASE_URL: str  # required environment variable

    JWT_SECRET: str  # required environment variable
    JWT_ALGORITHM: str = "HS256"  # optional environement variable with default value

    PROJECT_NAME: str = "FastAPI Sample Project"
    PROJECT_SUMMARY: str = "API for FastAPI Sample Project"
