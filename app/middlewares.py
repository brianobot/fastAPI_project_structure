import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.logger import logger
from app.settings import settings


async def log_request_middleware(request: Request, call_next):
    start = time.time()

    response: Response = await call_next(request)
    log_dict = {
        "url": request.url.path,
        "method": request.method,
        "status_code": response.status_code,
        "process_time": f"{(time.time() - start):.2f}s",
    }

    logger.info(log_dict)
    return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject over-sized request bodies before they are buffered into memory."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if (
            content_length is not None
            and content_length.isdigit()
            and int(content_length) > settings.MAX_REQUEST_BODY_BYTES
        ):
            return JSONResponse(
                status_code=413, content={"detail": "Request body too large"}
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline hardening headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS only makes sense over HTTPS; enable it outside local/dev.
        if not settings.DEBUG:
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=31536000; includeSubDomains"
        return response


class AllowAuthorizedDocAccess(BaseHTTPMiddleware):
    # WARNING: `request.client.host` is the *proxy's* IP unless the app runs
    # with --proxy-headers behind a trusted proxy. If your reverse proxy is
    # co-located (e.g. on 127.0.0.1) and proxy headers are NOT enabled, every
    # request appears to come from this list and the docs are exposed to all.
    # Prefer gating docs by DEBUG in production, or ensure --proxy-headers.
    allowed_ips = [
        "127.0.0.1",  # allows Viewing Docs in Local Development Environment
    ]
    # The interactive docs, ReDoc, and the raw OpenAPI schema all expose the
    # API surface, so all three must be gated - not just "/docs".
    protected_paths = ("/docs", "/redoc", "/openapi.json")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.protected_paths:
            client_ip = request.client.host if request.client else None
            # Docs are exposed when DEBUG is enabled OR the caller's IP is
            # whitelisted - so whitelisted IPs keep access even in production.
            docs_allowed = settings.DEBUG or client_ip in self.allowed_ips
            if not docs_allowed:
                # Respond as if the route does not exist so unauthorized
                # callers cannot even confirm the docs are hosted here.
                return JSONResponse(
                    status_code=404,
                    content={
                        "detail": "This route does not exist",
                        "path": request.url.path,
                    },
                )

        response = await call_next(request)
        return response
