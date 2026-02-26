from datetime import datetime

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_lifespan():
    # We use ASGITransport to trigger the lifespan events
    async with app.router.lifespan_context(app):
        # assert any item you expect to be on the app instance like a lifespan
        pass


async def test_http_exception_handler():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Trigger a 404 which is an HTTPException
        response = await client.get("/non-existent-path")

        assert response.status_code == 404
        data = response.json()

        assert "detail" in data
        assert data["path"] == "/non-existent-path"
        assert "timestamp" in data
        # Ensure timestamp is valid ISO format
        assert datetime.fromisoformat(data["timestamp"])


async def test_global_exception_handler():
    # We force a route to crash by patching a router function or using a mock route
    # For a unit test on the handler itself, we can simulate the call:
    from unittest.mock import MagicMock

    from app.main import global_exception_handler

    mock_request = MagicMock()
    mock_request.url.path = "/crash"
    mock_exc = Exception("Something went wrong")

    response = await global_exception_handler(mock_request, mock_exc)

    assert response.status_code == 500
    assert response.body.decode().find("An unexpected error occurred") != -1


async def test_trusted_host_middleware_allowed():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as ac:
        response = await ac.get("/")
        # We don't care about the result of the route, just that it's not a 400 Host error
        assert response.status_code != 400


async def test_trusted_host_middleware_denied():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://evil-attacker.com"
    ) as ac:
        response = await ac.get("/")
        assert response.status_code == 400
        assert response.text == "Invalid host header"


# Uncomment this to activate test after setting up CORS
async def _test_cors_middleware_headers():
    # Change the value of the CORS url here to match your config
    headers = {"Origin": "http://localhost:3000"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.options("/", headers=headers)
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
