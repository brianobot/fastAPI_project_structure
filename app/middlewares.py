import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.logger import logger


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


class AllowAuthorizedDocAccess(BaseHTTPMiddleware):
    allowed_ips = [
        "127.0.0.1",  # allows Viewing Docs in Local Development Environment
    ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host  # type: ignore

        if "/docs" in request.url.path:
            if client_ip not in self.allowed_ips:
                return JSONResponse(
                    status_code=500, content="Application Has Crashed 😭"
                )

        response = await call_next(request)
        return response
