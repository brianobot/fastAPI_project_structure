# FastAPI Project Structure Template
⚙️ You can Generate Project Interactively Based on this template with the [FastAPI Gen8 CLI Tool](https://pypi.org/project/fastapi-gen8/)


![Test Coverage Badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/brianobot/b56b3d61a5e739fd26252cda094bace2/raw)


[📖 Read Article here](https://medium.com/@brianobot9/the-ultimate-fastapi-project-blueprint-build-scalable-secure-and-maintainable-systems-with-ease-acbc4e058012)

This repository provides a clean and scalable template for building FastAPI applications. It is designed to help you start new projects quickly with best practices in mind.

## ⚡️ Features Included
- 📘 Organized project structure
- 🗒️ [Predefined Environment Configuration](./app/settings.py) with [Pydantic-Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- 🛜 Dependency management Setup for [Common Dependencies](./app/dependencies.py)
  - `get_db`: Async Database Session Dependency
  - `get_current_user`: Async User dependency. Extracts the user from the request's access token, and raises a 401 if the token is missing, invalid, blacklisted, or is not an **access** token.

- 👤 Initial [User Model](./app/models/auth.py) and [User Authentication Endpoints](./app/routers/auth.py) with [Unit Tests](./app/routers/tests/test_auth.py)
- 🔐 Full JWT auth flow: signup → email activation, sign-in issuing separate **access** and **refresh** tokens (each tagged with a `type` claim so they are not interchangeable), password reset, profile update, and logout via a Redis token blacklist.
- 🧰 Async [Redis manager](./app/redis_manager.py) (`redis.asyncio`) backing the token blacklist and short-lived one-time codes (activation / password reset).
- 🔒 Docs (`/docs`, `/redoc`, `/openapi.json`) gated behind a `DEBUG` flag **or** an IP allowlist — hidden with a 404 otherwise.
- 🚦 Per-endpoint rate limiting on the auth routes via [`slowapi`](./app/limiter.py), plus per-account lockout after repeated bad codes (brute-force protection on login and code endpoints).
- 🩺 `/health` readiness probe and a startup connectivity check for the database and Redis.
- 📝 [Predefined Logging](./app/logger.py) Configuration
- ⚙️ Unit Test Configuration with Pytest (With Async Support)
- ⏺️ [Alembic Data Migration](./alembic) Configuration and [alembic.ini](alembic.ini)


## Getting Started
> Requires **Python 3.12+** (the codebase uses PEP 695 generic syntax).

In order to get started with the FastAPI Project, follow the following steps
- [ ] Activate Project Python Virtual Environment
   ```bash
    source venv/bin/activate # this is for Unix systems
    ```
- [ ] Create an .env file from the .env.example file and provide values for missing environment variables
      - 1. Update the DATABASE_URL to point at an accessible DATABASE server
      - 2. Update the MAIL_CONFIG section to include mail server credentials
      - 3. Set `DEBUG=True` for local development (also exposes the interactive docs — see Quirks)
- [ ] Ensure a **Redis** server is running and reachable at `REDIS_HOST`/`REDIS_PORT` (defaults to `localhost:6379`). The auth flows and the test suite talk to a real Redis instance.
- [ ] Install ```make``` if you do not already have it and run the command ```make run-local``` to start you local server
- [ ] Apply Initial Database Migration for Ensure Database Connection string is valid
      ```bash
      alembic upgrade head
      ```
- [ ] Ensure the Setup Is Complete and Sucessful by Running the following command
      ```bash
      make test-local
      ```
      If all the tests pass successfully you're good to start working on your project.

- [ ] Start Local Server with the following command
      ```bash
      make run-local
      ```

## Architecture

The template is **async-first** and organizes each feature across four layers. When you add a feature, follow the same shape the `auth` feature uses:

| Layer | Responsibility |
| --- | --- |
| [`routers/`](./app/routers) | HTTP endpoints, dependency wiring, and `response_model`. Kept **thin** — no business logic. |
| [`services/`](./app/services) | Business logic: DB queries, token/password/email orchestration, Redis access. |
| [`schemas/`](./app/schemas) | Pydantic request/response models — all validation lives here. |
| [`models/`](./app/models) | SQLAlchemy ORM models (persistence). All inherit `AbstractBase` → UUID PK + `date_created`/`date_updated`. |

Request flow: a router aggregates into [`app/api_router.py`](./app/api_router.py) under the `/v1` prefix, which is mounted in [`app/main.py`](./app/main.py). `main.py` also assembles the middleware stack (CORS → GZip → TrustedHost → docs gate → request logging), a `slowapi` rate limiter, and uniform JSON exception handlers.

Supporting singletons: [`redis_manager`](./app/redis_manager.py) (async Redis for the token blacklist and one-time codes) and [`send_mail`](./app/mailer.py) (Jinja templates from `app/templates/`, always dispatched via FastAPI `BackgroundTasks`).

### Paginated responses

[`app/schemas/__init__.py`](./app/schemas/__init__.py) provides a reusable generic envelope for list endpoints, `PaginatedResponse[T]`, so paginated payloads share one consistent shape:

| Field | Meaning |
| --- | --- |
| `total_results` | total rows matching the query |
| `current_page` | 1-based page number returned |
| `total_pages` | total number of pages |
| `per_page` | page size used |
| `results` | the page of items, typed as `list[T]` |

Parameterize it with the item schema and use it as the endpoint's `response_model`:

```python
from app.schemas import PaginatedResponse
from app.schemas.auth import UserModel

@router.get("/users", response_model=PaginatedResponse[UserModel])
async def list_users(db: DBDep, page: int = 1, per_page: int = 20):
    # ... run the query, collect `users` and `total_results` ...
    return PaginatedResponse[UserModel](
        total_results=total_results,
        current_page=page,
        total_pages=-(-total_results // per_page),  # ceiling division
        per_page=per_page,
        results=users,
    )
```

> The model uses PEP 695 generic syntax (`class PaginatedResponse[T]`), which needs **Python 3.12+** and **mypy ≥ 1.12** — the CI workflows and the pre-commit `mypy` pin are set accordingly. On an older toolchain you'd see `Name "T" is not defined`; bump the versions (or fall back to the classic `Generic[T]` + `TypeVar` form).

## Project Structure

```
fastapi-project-structure/
.
├── Makefile
├── app
│   ├── __init__.py
│   ├── api_router.py
│   ├── database.py
│   ├── dependencies.py
│   ├── logger.py
│   ├── main.py
│   ├── middlewares.py
│   ├── models
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── routers
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── schemas
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── services
│   │   ├── __init__.py
│   │   └── auth.py
│   └── settings.py
├── logs
└── requirements.txt
```

## Quirks & Gotchas

Things that are easy to trip over when building on this template:

- **Alembic only sees models imported in [`app/models/__init__.py`](./app/models/__init__.py).** After adding a model, import it there (and add it to `__all__`) *before* running `alembic revision --autogenerate` — otherwise the migration silently misses your table.
- **Redis is required and its client is async.** Auth flows (logout blacklist, activation/reset codes) and the test suite hit a real Redis server. Every `redis_manager` call is a coroutine — `await` it. The test suite closes the connection pool after each test (autouse fixture in [`conftest.py`](./conftest.py)) because `pytest-asyncio` gives each test its own event loop; a shared `redis.asyncio` pool would otherwise reuse a closed-loop socket and raise `Event loop is closed`.
- **Docs are gated by `DEBUG` OR the IP allowlist.** The [`AllowAuthorizedDocAccess`](./app/middlewares.py) middleware serves `/docs`, `/redoc`, and `/openapi.json` only when `settings.DEBUG` is true **or** the client IP is in `allowed_ips` (default `127.0.0.1`); otherwise it returns a 404 that hides their existence. Note this middleware runs **before** `TrustedHostMiddleware`, so a request that clears the docs gate must still use a host listed in `main.py`'s `allowed_hosts`.
- **Access and refresh tokens are not interchangeable.** Each carries a `type` claim (`access` / `refresh`). `get_current_user` rejects anything that isn't an access token; the `refresh_token` endpoint rejects anything that isn't a refresh token.
- **Refresh tokens are single-use (rotated).** Each call to `/refresh_token` blacklists the presented refresh token and returns a fresh access **and** refresh token, so a leaked refresh token is usable at most once.
- **Logout is global, and so is a password change.** Logout blacklists the presented token(s) *and* bumps a per-user token version in Redis, so **every** token issued before it is invalidated across all devices (tokens carry a `ver` claim checked on each request). A successful **password reset or change** bumps the same version — revoking all existing sessions, including the current one. Reusing an already-rotated refresh token is treated as theft and revokes the whole family.
- **Baseline security headers** are added to every response by `SecurityHeadersMiddleware` (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and HSTS outside `DEBUG`). No CSP is set, to avoid breaking Swagger UI.
- **Behind a proxy, run with forwarded headers** (`make run-prod` / `uvicorn --proxy-headers --forwarded-allow-ips=...`) — otherwise per-IP rate limiting and logging see the load balancer's IP, not the client's.
- **Repeated bad codes lock the account.** After `MAX_CODE_ATTEMPTS` (default 5) wrong activation/reset codes, that account is locked for `CODE_LOCKOUT_SECONDS`; a successful attempt clears the counter.
- **`/health` and startup checks.** `/health` returns 503 if the DB or Redis is unreachable. On boot the app pings both; in production (`DEBUG=False`) it refuses to start if either is down, in `DEBUG` it only logs.
- **Sign-in requires a verified email.** `signin_user` returns `403 Email not verified` until activation flips `is_verified`. In tests, `UserFactory` builds verified users; use `create_user`/an unverified user to exercise the rejection.
- **Auth endpoints are rate-limited** via `slowapi` (`@limiter.limit` in [`app/routers/auth.py`](./app/routers/auth.py), registered in [`app/main.py`](./app/main.py)). Limits are **Redis-backed** ([`app/limiter.py`](./app/limiter.py)) so they hold across workers/replicas. The limiter is **disabled in the test suite** (`conftest.py`) since the counter is shared across tests — enable it per-test (with a unique client key) to assert 429s.
- **Access tokens are short-lived; sign secrets are enforced in production.** Access tokens default to 15 minutes (`ACCESS_TOKEN_LIFESPAN_MIN`), refresh tokens to 28 days (`REFRESH_TOKEN_LIFESPAN_DAYS`). With `DEBUG=False`, an empty `JWT_SECRET` makes the app refuse to start.
- **One-time codes are single-use and cryptographically random.** Activation and password-reset codes come from `secrets` and are deleted from Redis on successful use, so they can't be replayed.
- **`app/main.py` contains `{{ project_name }}`-style placeholders** (title/version/summary). These are template placeholders meant to be filled in per project, not bugs.
- **Mail sends with `VALIDATE_CERTS=True`.** If your dev SMTP uses a self-signed certificate, adjust the `ConnectionConfig` in [`app/mailer.py`](./app/mailer.py).

## How to Download Complete Project Structure from Github

1. **Clone the repository:**
    ```bash
    git clone https://github.com/brianobot/fastAPI_project_structure.git
    cd fastAPI_project_structure
    ```

2. **Create & Activate Virtual Environment to Manage Project Dependency In Isolation**
    ```bash
    python3 -m venv venv && source venv/bin/activate #for unix computers
    ```

3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Run the application:**
    ```bash
    make run-local # or uvicorn app.main:app --reload
    ```

5. **Access the API docs:**
    - Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.


## Testing
Run initial tests using pytest:
```bash
make test-local # or pytest
```

or

Run Specific tests
```bash
pytest -s app/routers/tests/test_auth.py
```

## Environment Variables

Copy `.env.example` to `.env` and update the values as needed. Notable keys:

- `DATABASE_URL` (required) — async driver expected, e.g. `postgresql+asyncpg://...`
- `DEBUG` (default `False`) — when `True`, exposes the interactive docs to all clients (see Quirks)
- `REDIS_HOST` / `REDIS_PORT` (default `localhost` / `6379`)
- `JWT_SECRET` — signing key; **required when `DEBUG=False`** (the app refuses to boot with an empty secret in production). `JWT_ALGORITHM` defaults to `HS256`.
- `ACCESS_TOKEN_LIFESPAN_MIN` (default `15`, **minutes**) / `REFRESH_TOKEN_LIFESPAN_DAYS` (default `28`, days)
- `MAIL_*` — SMTP credentials used by the mailer


## Upgrading an Existing Project
Backporting these changes into a project scaffolded from an older version of the
template? Follow [UPGRADING.md](./UPGRADING.md) — it isolates each change so you
can apply them independently, and keeps rate limiting an optional, skippable step.

## Contributing
Contributions are welcome! Please open issues or submit pull requests.
