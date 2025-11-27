from contextlib import asynccontextmanager
from datetime import datetime, UTC

from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi import HTTPException
from fastapi import FastAPI

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.logger import logger
from app.api_router import api
from app.settings import Settings
from app.middlewares import log_request_middleware

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def initiate_app():
    app = FastAPI(
        title="FastAPI Sample Project",
        summary="API for FastAPI Sample Project",
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
            "127.0.0.1",
            "localhost",
            # Add allowed hosts here
        ],
    )
    app.add_middleware(BaseHTTPMiddleware, dispatch=log_request_middleware)

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter

    app.include_router(api)
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "path": request.url.path,
        },
    )
