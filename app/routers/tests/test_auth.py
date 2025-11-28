import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.main import app
from app.models import User as UserDB
from app.schemas.auth import UserModel


async def test_signup_succeeds(client: AsyncClient, signup_data: dict[str, str]):
    response = await client.post("/v1/auth/signup", json=signup_data)
    assert response.status_code == 200
    response_data = response.json()
    assert UserModel.model_validate(response_data)


@pytest.mark.parametrize(
    "invalid_signup_data,status_code,error_message",
    [
        (
            {
                "email": "emailemail.com",
                "password": "password",
            },
            422,
            "value is not a valid email address: An email address must have an @-sign.",
        ),
        (
            {
                "email": "seemail@email.com",
                "password": "paword",
            },
            422,
            "String should have at least 8 characters",
        ),  
        (
            {
                "email": f"email@{'email' * 21}.com",
                "password": "password",
            },
            422,
            "value is not a valid email address: After the @-sign, periods cannot be separated by so many characters (42 characters too many).",
        ),
    ],
)
async def test_signup_fails(
    client: AsyncClient, invalid_signup_data: dict, status_code: int, error_message: str
):
    response: Response = await client.post("/v1/auth/signup", json=invalid_signup_data)
    assert response.status_code == status_code
    response_data = response.json().get("detail")
    error_msg = response_data[0].get("msg")
    assert error_msg == error_message


@pytest.fixture
async def sign_up_user(signup_data: dict):
    # to be used as a side effect to test things that need a user that has signed up
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post("/v1/auth/signup", json=signup_data)


async def mutate_cache_item(key: str, value: dict):
    # to be used as a side effect to mutate cache item
    from app.redis_manager import redis_manager

    redis_manager.cache_json_item(key, value)


async def test_initiate_password_reset(client: AsyncClient, signup_data: dict):
    data = {"email": signup_data["email"]}
    response: Response = await client.post(
        "/v1/auth/initiate_password_reset", json=data
    )
    assert response.status_code == 200
    assert response.json().get("detail") == "Password reset code sent"


async def test_verify_reset_password_otp(client: AsyncClient, user: UserDB):
    await mutate_cache_item(f"reset-code-{user.email}", {"code": "0000"})
    data = {"email": user.email, "code": "0000"}
    response: Response = await client.post("/v1/auth/verify_password_reset", json=data)
    assert response.status_code == 200
    assert response.json().get("detail") == "Code is Correct"


async def test_reset_password(client: AsyncClient, user: UserDB):
    await mutate_cache_item(f"reset-code-{user.email}", {"code": "0000"})
    data = {"new_password": "password", "email": user.email, "code": "0000"}
    response: Response = await client.post("/v1/auth/reset_password", json=data)
    assert response.status_code == 200
    assert response.json().get("detail") == "Password reset successfully"


async def test_reset_password_fails(client: AsyncClient, user: UserDB):
    await mutate_cache_item(f"reset-code-{user.email}", {"code": "0000"})
    data = {"new_password": "password", "email": user.email, "code": "1111"}
    response: Response = await client.post("/v1/auth/reset_password", json=data)
    assert response.status_code == 400
    assert response.json().get("detail") == "Invalid Reset Code"


async def test_signin(client: AsyncClient, user: UserDB):
    data = {
        "username": user.email,
        "password": "password",
    }
    response: Response = await client.post("/v1/auth/token", data=data)
    assert response.status_code == 200
    response_data = response.json()
    assert "token_type" in response_data
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert "access_expires_at" in response_data
    assert "refresh_expires_at" in response_data


async def test_get_refresh_token(client: AsyncClient, user: UserDB):
    login_data = {"username": user.email, "password": "password"}
    refresh_token = (
        (await client.post("/v1/auth/token", data=login_data))
        .json()
        .get("refresh_token")
    )
    data = {"refresh_token": refresh_token}
    response: Response = await client.post("/v1/auth/refresh_token", json=data)
    assert response.status_code == 200
    response_data = response.json()
    assert "token_type" in response_data
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert "access_expires_at" in response_data
    assert "refresh_expires_at" in response_data


async def test_get_user_detail(client: AsyncClient, user: UserDB):
    login_data = {"username": user.email, "password": "password"}
    access_token = (
        (await client.post("/v1/auth/token", data=login_data))
        .json()
        .get("access_token")
    )
    response: Response = await client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "id" in response_data
    assert "email" in response_data


@pytest.mark.parametrize(
    "update_data,status_code,error_message",
    [
        ({"old_password": "password", "new_password": "new_password"}, 202, ""),
    ],
)
async def test_update_user_detail(
    client: AsyncClient,
    user: UserDB,
    update_data: dict,
    status_code: int,
    error_message: str,
):
    login_data = {"username": user.email, "password": "password"}
    access_token = (
        (await client.post("/v1/auth/token", data=login_data))
        .json()
        .get("access_token")
    )
    response: Response = await client.patch(
        "/v1/auth/me",
        json=update_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status_code
    if status_code == 202:
        response_data = response.json()
        assert "id" in response_data
        assert "email" in response_data

