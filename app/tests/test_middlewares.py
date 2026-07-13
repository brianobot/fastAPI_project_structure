import uuid

from httpx import ASGITransport, AsyncClient

from app import middlewares
from app.limiter import limiter
from app.main import app


def make_client(ip: str, host: str = "localhost") -> AsyncClient:
    # Pair a client IP with a trusted host so requests that pass the doc-access
    # gate still clear TrustedHostMiddleware (which runs after it).
    transport = ASGITransport(app=app, client=(ip, 12345))
    return AsyncClient(transport=transport, base_url=f"http://{host}")


async def test_docs_served_in_debug_regardless_of_ip(monkeypatch):
    # DEBUG alone is enough, even for a non-whitelisted IP.
    monkeypatch.setattr(middlewares.settings, "DEBUG", True)
    async with make_client("10.0.0.5") as ac:
        docs = await ac.get("/docs")
        schema = await ac.get("/openapi.json")
    assert docs.status_code == 200
    assert schema.status_code == 200


async def test_docs_served_for_whitelisted_ip_when_debug_off(monkeypatch):
    # A whitelisted IP keeps access even with DEBUG off.
    monkeypatch.setattr(middlewares.settings, "DEBUG", False)
    async with make_client("127.0.0.1") as ac:
        docs = await ac.get("/docs")
        schema = await ac.get("/openapi.json")
    assert docs.status_code == 200
    assert schema.status_code == 200


async def test_docs_hidden_when_debug_off_and_ip_not_whitelisted(monkeypatch):
    # Both gates closed -> the docs are hidden.
    monkeypatch.setattr(middlewares.settings, "DEBUG", False)
    async with make_client("10.0.0.5") as ac:
        docs = await ac.get("/docs")
        schema = await ac.get("/openapi.json")
    assert docs.status_code == 404
    assert schema.status_code == 404


async def test_rate_limit_returns_429(monkeypatch):
    # The limiter is disabled globally for tests; enable it just for this one.
    # /resend_activation is capped at 3/minute, so the 4th+ call is rejected.
    # Use a unique client key so the Redis-backed counter can't carry residual
    # counts from a previous run into this one.
    monkeypatch.setattr(limiter, "enabled", True)
    async with make_client(uuid.uuid4().hex) as ac:
        statuses = [
            (
                await ac.post(
                    "/v1/auth/resend_activation", json={"email": "ghost@example.com"}
                )
            ).status_code
            for _ in range(5)
        ]
    assert statuses.count(200) == 3
    assert statuses.count(429) == 2
