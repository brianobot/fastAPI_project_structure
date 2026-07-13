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

    # Reject request bodies larger than this (anti memory-exhaustion DoS).
    MAX_REQUEST_BODY_BYTES: int = 1024 * 1024  # 1 MB
    # Backstop rate limit applied to every route (stricter per-route limits
    # via @limiter.limit still take precedence).
    RATE_LIMIT_DEFAULT: str = "120/minute"

    MAIL_USERNAME: str  # required environment variable
    MAIL_PASSWORD: str  # required environment variable
    MAIL_FROM: str  # required environment variable
    MAIL_PORT: str  # required environment variable
    MAIL_SERVER: str  # required environment variable
    MAIL_FROM_NAME: str  # required environment variable

    # HS256 security rests entirely on this secret's strength; a short/guessable
    # value lets an attacker forge tokens and bypass every downstream control.
    MIN_JWT_SECRET_LENGTH: int = 32

    @model_validator(mode="after")
    def _require_strong_jwt_secret_in_production(self) -> "Settings":
        # Enforced only outside DEBUG so local/dev stays frictionless; production
        # refuses to boot on a missing or weak secret.
        if not self.DEBUG and len(self.JWT_SECRET) < self.MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "JWT_SECRET must be set to at least "
                f"{self.MIN_JWT_SECRET_LENGTH} characters when DEBUG is False. "
                'Generate one with: python -c "import secrets; '
                'print(secrets.token_urlsafe(64))"'
            )
        return self


# Shared, import-once settings instance. Import this rather than calling
# Settings() again - each call re-reads and re-parses the .env file.
settings = Settings()  # type: ignore
