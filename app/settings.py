from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str  # required environment variable

    JWT_SECRET: str = "" # Optional environment variable but unsafe
    JWT_ALGORITHM: str = "HS256"  # optional environement variable with default value
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    MAIL_USERNAME: str  # required environment variable
    MAIL_PASSWORD: str  # required environment variable
    MAIL_FROM: str      # required environment variable
    MAIL_PORT: str      # required environment variable
    MAIL_SERVER: str    # required environment variable
    MAIL_FROM_NAME: str # required environment variable
