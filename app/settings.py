from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    example_secret: str = "example secret value"

    DATABASE_URL: str  # required environment variable

    JWT_SECRET: str = "" # required environment variable
    JWT_ALGORITHM: str = "HS256"  # optional environement variable with default value
