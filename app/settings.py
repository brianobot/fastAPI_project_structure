from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str  # required environment variable
    DEBUG: bool = False

    ACCESS_TOKEN_LIFESPAN_MIN: int = 15
    REFRESH_TOKEN_LIFESPAN_DAYS: int = 28

    JWT_SECRET: str = ""  # REQUIRED in production (DEBUG=False); see validator below
    JWT_ALGORITHM: str = "HS256"  # optional environement variable with default value

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    MAIL_USERNAME: str  # required environment variable
    MAIL_PASSWORD: str  # required environment variable
    MAIL_FROM: str  # required environment variable
    MAIL_PORT: str  # required environment variable
    MAIL_SERVER: str  # required environment variable
    MAIL_FROM_NAME: str  # required environment variable

    @model_validator(mode="after")
    def _require_jwt_secret_in_production(self) -> "Settings":
        # An empty JWT_SECRET signs forgeable tokens. Allow it only in DEBUG
        # (local/dev); refuse to boot in production so the misconfig is loud.
        if not self.DEBUG and not self.JWT_SECRET:
            raise ValueError("JWT_SECRET must be set when DEBUG is False")
        return self


# Shared, import-once settings instance. Import this rather than calling
# Settings() again - each call re-reads and re-parses the .env file.
settings = Settings()  # type: ignore
