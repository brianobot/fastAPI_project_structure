from slowapi import Limiter
from slowapi.util import get_remote_address

from app.settings import settings

# Shared rate limiter, keyed by client IP. Backed by Redis so limits are
# enforced consistently across every worker/replica (an in-memory store would
# give each process its own counter and reset on restart). Import this in
# routers to decorate endpoints with `@limiter.limit(...)`, and register it on
# the app in main.py.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
)
