import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.main import app


# Lazy override of the global client fixture to patch the ip address
@pytest.fixture
async def client():
    transport = ASGITransport(
        app=app,
        client=("10.0.0.5", 12345),
    )
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def test_docs_route_is_whitelisted(client: AsyncClient):
    response: Response = await client.get("/docs")
    assert response.status_code == 500
