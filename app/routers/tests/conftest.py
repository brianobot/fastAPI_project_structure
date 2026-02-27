import faker
import pytest
from httpx import AsyncClient

from app.models.auth import User as UserDB

faker = faker.Faker()


@pytest.fixture
async def signup_data() -> dict[str, str]:
    return {
        "email": faker.email(),
        "password": faker.password(length=8),
    }


@pytest.fixture
async def access_token(client: AsyncClient, user: UserDB):
    res = await client.post(
        "/v1/auth/token", data={"username": user.email, "password": "password"}
    )
    return res.json().get("access_token")


@pytest.fixture
async def auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}
