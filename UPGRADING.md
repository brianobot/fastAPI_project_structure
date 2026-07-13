# Upgrading an Older Project

This guide backports the recent security, correctness, and structural fixes into
a project that was scaffolded from an **earlier version** of this template.

It is written so you can adopt everything **without turning on rate limiting** —
that step is isolated near the end and is safe to skip. Every other step is
independent, so apply them in any order you like and run your tests after each.

> Conventions below: `app/...` paths are relative to your project. Snippets show
> the **target** state; adapt names if yours differ.

---

## 0. Compatibility at a glance

| Change | Type | Action needed |
| --- | --- | --- |
| Shared `settings` singleton | Safe | Mechanical import swap |
| Async Redis (`redis.asyncio`) | **Breaking (code)** | Add `await` to every `redis_manager` call |
| Token `type` claims (access/refresh) | **Breaking (tokens)** | Old tokens lack `type`; see §4 |
| Logout blacklist TTL + refresh rotation | Behavioral | Review logout/refresh clients |
| `is_verified` server default + sign-in enforcement | **Breaking (data)** | Backfill existing users; see §6 |
| Docs gated by `DEBUG` **or** IP allowlist | Behavioral | Set `DEBUG`; see §7 |
| `secrets` for codes, mailer `VALIDATE_CERTS=True` | Safe | Drop-in |
| Short-lived access tokens + `JWT_SECRET` fail-fast | Behavioral | Set lifespans/secret; see §9 note |
| Health check + startup connectivity | Safe (additive) | See §10 |
| Global logout (token versioning) | **Breaking (tokens)** | Adds `ver` claim; see §11 |
| Account lockout on codes | Behavioral | See §12 |
| Rate limiting | **Optional** | Skip it — see §13 |
| Revoke sessions on password change + reuse detection | Behavioral | See §14 |
| Security response headers | Safe (additive) | See §15 |
| Proxy headers behind a load balancer | Deploy config | See §16 |
| CI hardening (SAST, lint gate, coverage floor) | Safe (additive) | See §17 |

**Backup first:** commit or branch before starting, and snapshot your database
before running the migration in §6.

---

## 1. Dependencies

Make sure these are installed and pinned in `requirements.txt`:

```
redis>=4.2          # provides redis.asyncio
slowapi==0.1.9      # only if you do the OPTIONAL rate-limiting step (§13)
```

If you skip §13 you do **not** need `slowapi`.

---

## 2. Shared settings singleton

Re-parsing `.env` in every module is wasteful. Define one instance and import it.

In `app/settings.py`, add at the bottom:

```python
# Import this instead of calling Settings() again.
settings = Settings()  # type: ignore
```

Then in each module that had `settings = Settings()`, replace:

```python
from app.settings import Settings
settings = Settings()  # type: ignore
```

with:

```python
from app.settings import settings
```

Also add the flags used later, in the `Settings` class body:

```python
DEBUG: bool = False
ACCESS_TOKEN_LIFESPAN_MIN: int = 15    # minutes
REFRESH_TOKEN_LIFESPAN_DAYS: int = 28  # days
```

---

## 3. Async Redis (breaking — needs `await`)

Switch the client to `redis.asyncio` so cache calls stop blocking the event loop.

`app/redis_manager.py`:

```python
import redis.asyncio as redis   # was: import redis

class RedisManager:
    def __init__(self):
        self.redis_client = redis.Redis(host=settings.REDIS_HOST,
                                         port=settings.REDIS_PORT,
                                         decode_responses=True)

    async def cache_json_item(self, key, value, ttl=3600) -> None:
        await self.redis_client.set(name=key, value=json.dumps(value), ex=ttl)

    async def get_json_item(self, key, default=None):
        value = await self.redis_client.get(name=key)
        return default if value is None else json.loads(value)

    async def delete_key(self, key) -> None:
        await self.redis_client.delete(key)

    # Helpers used by §11 (token versioning) and §12 (lockout counters):
    async def get_int(self, key) -> int:
        value = await self.redis_client.get(name=key)
        return int(value) if value is not None else 0

    async def increment(self, key, ttl=None) -> int:
        value = await self.redis_client.incr(key)
        if ttl is not None and value == 1:      # set expiry on first increment
            await self.redis_client.expire(key, ttl)
        return value
```

**Now add `await` to every call site** — search your codebase:

```bash
grep -rn "redis_manager\.\(cache_json_item\|get_json_item\|delete_key\)" app/
```

Each hit inside an `async def` gets an `await`. This includes
`get_current_user` (the logout blacklist check) and your auth service functions.

**Test fixture (required).** `pytest-asyncio` gives each test its own event loop,
but a module-level async Redis client pools connections bound to a closed loop →
`RuntimeError: Event loop is closed`. Close the pool after each test. In your root
`conftest.py`:

```python
from app.redis_manager import redis_manager

@pytest.fixture(autouse=True)
async def close_redis_connections():
    yield
    await redis_manager.redis_client.aclose()
```

Direct `redis_manager` calls in your tests also need `await` (and any sync test
that touches Redis must become `async def`).

---

## 4. Token `type` claims (access vs refresh)

Tag tokens so an access token can't be used where a refresh token is expected and
vice versa.

In your token creators (`app/services/auth.py`):

```python
to_encode.update({"exp": expire, "type": "access"})   # create_access_token
to_encode.update({"exp": expire, "type": "refresh"})  # create_refresh_token
```

In `get_current_user` (`app/dependencies.py`), after decoding and reading `sub`:

```python
if payload.get("type") != "access":
    raise credentials_exception
```

In the `refresh_token` service, after decoding:

```python
if payload.get("type") != "refresh":
    raise HTTPException(status_code=401, detail="Invalid Refresh Token")
```

> **Migration note:** tokens issued before this change have **no `type` claim**,
> so they will be rejected after you deploy. Expect all users to re-authenticate
> once. If you must avoid that, treat a *missing* `type` as `access` for a grace
> period (`payload.get("type", "access") != "access"`) and remove the fallback
> after your access-token lifetime has elapsed.

---

## 5. Logout TTL + refresh rotation

**Blacklist for the token's real remaining life** (not a fixed TTL). Add a helper
and use it from logout:

```python
async def blacklist_token(token: str) -> None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError:
        return
    exp = payload.get("exp")
    ttl = int(exp - datetime.now(UTC).timestamp()) if exp else 0
    if ttl > 0:
        await redis_manager.cache_json_item(token, {"timestamp": str(datetime.now(UTC))}, ttl=ttl)
```

Let the logout route accept an optional refresh token so it can be revoked too
(add a `LogoutData(refresh_token: str | None = None)` schema and pass it through).

**Refresh rotation.** In `refresh_token`, reject blacklisted tokens, then rotate:

```python
if await redis_manager.get_json_item(token_data.refresh_token):
    raise HTTPException(status_code=401, detail="Invalid Refresh Token")
# ...decode, validate type == "refresh", load user...
email = payload.get("sub")
if not isinstance(email, str):
    raise HTTPException(status_code=401, detail="Invalid Refresh Token")
# ...
await blacklist_token(token_data.refresh_token)          # single-use
new_access  = create_access_token({"sub": email},  ACCESS_TOKEN_LIFESPAN)
new_refresh = create_refresh_token({"sub": email}, REFRESH_TOKEN_LIFESPAN)
```

**Client impact:** `/refresh_token` now returns a **new** refresh token each time;
clients must store and use the returned one. The old one stops working.

---

## 6. `is_verified` (data-breaking — read carefully)

Two parts: a schema default, and — only if you want it — sign-in enforcement.

**a) Add the column / server default.** If your `User` model lacks `is_verified`,
add it. Give it a server default so raw inserts and existing rows are covered:

```python
from sqlalchemy import Boolean, false
is_verified: Mapped[bool] = mapped_column(
    Boolean, default=False, server_default=false(), nullable=False
)
```

Generate a migration and, **critically, backfill existing users** so you don't
lock everyone out:

```python
def upgrade():
    # add column if it doesn't exist yet, then:
    op.alter_column("users", "is_verified",
                    existing_type=sa.Boolean(), existing_nullable=False,
                    server_default=sa.false())
    # Existing accounts predate verification — treat them as verified:
    op.execute("UPDATE users SET is_verified = true")
```

**b) (Optional) Enforce it at sign-in.** This is a behavioral break — do it only
after the backfill above, or unverified legacy users can't log in:

```python
if not user.is_verified:
    raise HTTPException(status_code=403, detail="Email not verified")
```

If you use factories in tests, set `is_verified = True` on the user factory so the
rest of your auth tests keep signing in.

---

## 7. Docs gating (`DEBUG` **or** IP allowlist)

Serve `/docs`, `/redoc`, and `/openapi.json` only when `DEBUG` is on **or** the
caller IP is whitelisted; otherwise return a 404 that hides their existence.
In your `AllowAuthorizedDocAccess` middleware:

```python
protected_paths = ("/docs", "/redoc", "/openapi.json")

async def dispatch(self, request, call_next):
    if request.url.path in self.protected_paths:
        client_ip = request.client.host if request.client else None
        if not (settings.DEBUG or client_ip in self.allowed_ips):
            return JSONResponse(status_code=404,
                                content={"detail": "This route does not exist",
                                         "path": request.url.path})
    return await call_next(request)
```

**Watch out:** this middleware runs **before** `TrustedHostMiddleware`, so a
request that clears the docs gate must still use a host in your `allowed_hosts`.
Set `DEBUG=True` in your local `.env`; keep it `False` in production.

---

## 8. Cryptographically secure codes

Swap `random` for `secrets` in `generate_random_code`:

```python
import secrets

def generate_random_code(n: int = 4) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(n))
```

Also delete activation/reset codes from Redis after successful use
(`await redis_manager.delete_key(...)`) so they can't be replayed.

---

## 9. Mailer certs, short-lived tokens, and a required secret

- In `app/mailer.py`'s `ConnectionConfig`, set `VALIDATE_CERTS=True` (keep `False`
  locally only if your dev SMTP uses a self-signed cert).
- Drive token lifespans from settings (added in §2) — and note **access tokens are
  minutes, refresh tokens are days**:

  ```python
  ACCESS_TOKEN_LIFESPAN  = timedelta(minutes=settings.ACCESS_TOKEN_LIFESPAN_MIN)
  REFRESH_TOKEN_LIFESPAN = timedelta(days=settings.REFRESH_TOKEN_LIFESPAN_DAYS)
  ```

- Fail fast on a missing signing secret in production. In `Settings`:

  ```python
  from pydantic import model_validator

  @model_validator(mode="after")
  def _require_jwt_secret_in_production(self):
      if not self.DEBUG and not self.JWT_SECRET:
          raise ValueError("JWT_SECRET must be set when DEBUG is False")
      return self
  ```

---

## 10. Health check + startup connectivity

Add a readiness probe and validate connectivity on boot.

`app/routers/health.py`:

```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.redis_manager import redis_manager

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]):
    checks = {"database": "ok", "redis": "ok"}
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"
    try:
        await redis_manager.redis_client.ping()
    except Exception:
        checks["redis"] = "error"
    if any(v != "ok" for v in checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ok", "checks": checks}
```

Register it (`app.include_router(health_router)`), and check connectivity in the
lifespan — fail fast in production, warn in `DEBUG`:

```python
async def check_connectivity() -> None:
    problems = []
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        problems.append(f"database ({exc})")
    try:
        await redis_manager.redis_client.ping()
    except Exception as exc:
        problems.append(f"redis ({exc})")
    if problems:
        logger.error("Startup connectivity check failed: " + ", ".join(problems))
        if not settings.DEBUG:
            raise RuntimeError("Startup connectivity check failed")

@asynccontextmanager
async def lifespan(app):
    await check_connectivity()
    yield
```

> Requires the async Redis client from §3. Most test clients (`ASGITransport`)
> don't trigger the lifespan, so this won't run in typical tests; the `DEBUG`
> guard keeps any explicit lifespan test green even if the DB/Redis is down.

---

## 11. Global logout (token versioning)

Make logout invalidate **every** token a user holds, across all devices — not just
the pair presented. Requires the `get_int`/`increment` helpers from §3.

Give each token a unique id and the user's current version. In your token
creators (`app/services/auth.py`):

```python
import secrets

def token_version_key(email: str) -> str:
    return f"token-version-{email}"

# in create_access_token / create_refresh_token, when building the payload:
to_encode.update({"exp": expire, "type": "access",  "jti": secrets.token_hex(16)})
to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_hex(16)})
```

At login, read the version and embed it as a `ver` claim:

```python
version = await redis_manager.get_int(token_version_key(email))
access  = create_access_token({"sub": email, "ver": version},  ACCESS_TOKEN_LIFESPAN)
refresh = create_refresh_token({"sub": email, "ver": version}, REFRESH_TOKEN_LIFESPAN)
```

Reject stale tokens in `get_current_user` (and the same check in `refresh_token`,
re-embedding the current version on rotation):

```python
version = await redis_manager.get_int(auth_services.token_version_key(username))
if payload.get("ver", 0) != version:
    raise credentials_exception
```

Bump the version on logout (the route passes the authenticated `user.email`):

```python
async def logout(access_token, refresh_token=None, email=None):
    await blacklist_token(access_token)
    if refresh_token:
        await blacklist_token(refresh_token)
    if email:
        await redis_manager.increment(token_version_key(email))   # invalidate all
    return {"detail": "User Logged Out Successfully"}
```

> **Migration note:** old tokens have no `ver`; `payload.get("ver", 0)` treats them
> as version `0`, so they stay valid until the first logout for that user (which
> sets the version to `1`). **Keep `token-version-*` on a persistent Redis** (AOF/
> RDB) — if the key is evicted, the version resets to `0` and pre-logout tokens
> validate again. For stronger guarantees, store the version on the users table.

---

## 12. Account lockout on codes

Throttle brute-forcing of the 6-digit activation/reset codes per account (this is
account-level, complementing any per-IP rate limit). Uses `get_int`/`increment`
from §3.

```python
MAX_CODE_ATTEMPTS = 5
CODE_LOCKOUT_SECONDS = 15 * 60

async def guard_code_attempts(scope: str, email: str) -> str:
    key = f"failed-{scope}-{email}"
    if await redis_manager.get_int(key) >= MAX_CODE_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")
    return key
```

Wrap each code check (`activate_user`, `reset_password`):

```python
attempt_key = await guard_code_attempts("reset", email)     # or "activation"
data = await redis_manager.get_json_item(f"reset-code-{email}")
if not data or data.get("code") != submitted_code:
    await redis_manager.increment(attempt_key, ttl=CODE_LOCKOUT_SECONDS)
    raise HTTPException(status_code=400, detail="Invalid Reset Code")
# ...on success:
await redis_manager.delete_key(f"reset-code-{email}")
await redis_manager.delete_key(attempt_key)                 # clear the counter
```

> Apply this to the **code-guessing** endpoints, not login — account lockout on
> login lets an attacker lock out a victim (DoS). Guard login with the per-IP rate
> limit in §13 instead.

---

## 13. Rate limiting — OPTIONAL (skip to keep it inactive)

**You can stop here.** Everything above works without rate limiting. This section
is only if you *choose* to add it. Two ways to keep it inactive:

**Option A — don't add it at all.** Do nothing. No `slowapi` dependency, no
decorators. This is the "without rate limiting active" path.

**Option B — add the wiring but keep it switched off**, so you can flip it on
later per-environment. Add a setting:

```python
# app/settings.py
RATE_LIMIT_ENABLED: bool = False
```

Create `app/limiter.py` (Redis-backed so limits hold across workers/replicas):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.settings import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
    storage_uri=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
)
```

Register it in `app/main.py` (harmless while disabled):

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Decorate sensitive routes (each needs a `request: Request` parameter):

```python
@router.post("/token")
@limiter.limit("10/minute")
async def signin(request: Request, ...):
    ...
```

With `RATE_LIMIT_ENABLED=False` the decorators are no-ops, so behavior is
unchanged. Turn it on later by setting `RATE_LIMIT_ENABLED=True` in the target
environment. **In tests, keep it disabled** — the shared counter would let
unrelated tests exhaust each other's quota:

```python
# conftest.py
from app.limiter import limiter
limiter.enabled = False
```

If you enable it in a specific test, use a **unique client key per run** (the
Redis-backed counter persists across runs within the window) to avoid flakiness.

---

## 14. Revoke sessions on password change + refresh-reuse detection

Builds on the token versioning from §11.

**Kill all sessions when the password changes.** A reset/change usually means the
old credentials are compromised, so bump the token version after a successful
`reset_password` (and after a password change in `update_user`):

```python
async def invalidate_all_sessions(email: str) -> None:
    await redis_manager.increment(token_version_key(email))

# reset_password(), after the password UPDATE commits:
await invalidate_all_sessions(reset_data.email)

# update_user(), after the UPDATE commits, only when the password changed:
if new_password:
    await invalidate_all_sessions(email)
```

> A password *change* logs the user out of their **current** session too (the
> access token used for the request is invalidated for subsequent calls). That's
> the secure default; have the client re-authenticate afterward.

**Refresh-reuse detection.** A rotated refresh token should never come back. If a
blacklisted refresh token is presented again, treat it as theft and revoke the
whole family:

```python
if await redis_manager.get_json_item(token_data.refresh_token):
    try:
        stale = jwt.decode(token_data.refresh_token, JWT_SECRET,
                           algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        if isinstance(stale.get("sub"), str):
            await invalidate_all_sessions(stale["sub"])
    except InvalidTokenError:
        pass
    raise HTTPException(status_code=401, detail="Invalid Refresh Token")
```

**Readability tip (optional):** while you're here, move the Redis key formats into
builder functions (`activation_code_key`, `reset_code_key`, `failed_attempts_key`,
`token_version_key`) so formats and TTLs live in one place.

---

## 15. Security response headers

Add a middleware that stamps hardening headers on every response:

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.DEBUG:   # HSTS only over HTTPS
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

> A strict `Content-Security-Policy` is intentionally omitted — it breaks the
> Swagger UI (CDN + inline scripts). Add one scoped to your own frontend if needed.

---

## 16. Proxy headers behind a load balancer

Per-IP rate limiting and request logging read `request.client.host`. Behind a
proxy that's the **proxy's** IP unless you enable forwarded headers — so run:

```bash
uvicorn app.main:app --proxy-headers --forwarded-allow-ips="<proxy-ip>"
```

Restrict `--forwarded-allow-ips` to your proxy's address(es); `"*"` trusts any
client's `X-Forwarded-For` and is spoofable if you're not actually behind a proxy.

---

## 17. CI hardening (optional)

- **Replace the dead `safety check`** (it now needs an account) with SAST:
  `pip install bandit && bandit -r app -x <tests> --severity-level medium`.
- **Add a lint/type gate** — run `ruff`, `black --check`, `isort --check-only`,
  and `mypy app` as a CI job, not just in pre-commit.
- **Floor your coverage**: `coverage report --fail-under=90` so it can't silently
  regress.
- **Bump CI Python to 3.12+** if you adopted the `PaginatedResponse[T]` generic
  (PEP 695), and pin pre-commit `mypy` to ≥ 1.12.

---

## Verify

After applying the steps you want:

```bash
pytest -q                 # or: make test-local
```

Watch specifically for: un-`await`ed Redis calls (coroutine warnings), the
`Event loop is closed` error (missing §3 fixture), 401s from pre-`type`/pre-`ver`
tokens (§4/§11), and 403s from unverified legacy users (§6b backfill).

## Rollback

Every step is self-contained; revert individually via git. The only step with
persistent state is §6 — restore your database snapshot if you need to undo the
migration and backfill.
