from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api_router import api
from app.database import AsyncSessionLocal
from app.limiter import limiter
from app.logger import logger
from app.middlewares import (
    AllowAuthorizedDocAccess,
    MaxBodySizeMiddleware,
    SecurityHeadersMiddleware,
    log_request_middleware,
)
from app.redis_manager import redis_manager
from app.routers.health import router as health_router
from app.settings import settings


async def check_connectivity() -> None:
    """Fail fast (in production) if the DB or Redis is unreachable at startup."""
    problems = []
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        problems.append(f"database ({exc})")
    try:
        await redis_manager.redis_client.ping()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"redis ({exc})")

    if problems:
        message = "Startup connectivity check failed: " + ", ".join(problems)
        logger.error(message)
        # In DEBUG (local/dev) log and continue; in production refuse to start.
        if not settings.DEBUG:
            raise RuntimeError(message)
    else:
        logger.info("Startup connectivity check passed (database, redis)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_connectivity()
    yield


def initiate_app():
    app = FastAPI(
        title="{{ project_name }}",
        version="{{ project_version }}",
        summary="{{ project_description }}",
        lifespan=lifespan,
    )

    origins = [
        # Add allowed origins here
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # tweak this to see the most efficient size
    app.add_middleware(GZipMiddleware, minimum_size=100)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "test",
            "127.0.0.1",
            "localhost",
            # Add allowed hosts here
        ],
    )
    app.add_middleware(AllowAuthorizedDocAccess)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MaxBodySizeMiddleware)
    app.add_middleware(BaseHTTPMiddleware, dispatch=log_request_middleware)

    # Enforce rate limits: the default backstop (SlowAPIMiddleware) on every
    # route, plus stricter per-route @limiter.limit(...) declarations.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(api)
    app.include_router(health_router)
    return app


app = initiate_app()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "path": request.url.path,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@app.exception_handler(404)
async def custom_404_handler(request: Request, __: Exception):
    return JSONResponse(
        status_code=404,
        content={
            "detail": "This route does not exist",
            "path": request.url.path,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "path": request.url.path,
            "detail": "An unexpected error occurred",
        },
    )
