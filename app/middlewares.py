import time

from fastapi import Request, Response
from app.logger import logger


BLOCKED_IPS = []


async def log_request_middleware(request: Request, call_next):
    start = time.time()

    response: Response = await call_next(request)
    log_dict = {
        "url": request.url.path,
        "method": request.method,
        "process_time": f"{(time.time() - start):.2f}s",
        "status_code": response.status_code,
    }

    logger.info(log_dict)
    return response
