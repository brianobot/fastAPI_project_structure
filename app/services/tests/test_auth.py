from typing import Any

import pytest
from faker import Faker
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User as UserDB
from app.redis_manager import redis_manager
from app.routers.tests.conftest import signup_data  # noqa
from app.schemas import auth as auth_schemas
from app.schemas.auth import UserSignUpData
from app.services import auth as auth_services

faker = Faker()


async def test_get_password_hash_and_verify_password():
    password_hash = auth_services.get_password_hash("password")
    assert auth_services.verify_password("password", password_hash)


async def test_get_user(user: UserDB, session: AsyncSession):
    result = await auth_services.get_user(user.email, session)
    assert isinstance(result, UserDB)


async def test_get_user_return_none(session: AsyncSession):
    result = await auth_services.get_user(faker.email(), session)
    assert result is None


async def test_create_user(session: AsyncSession, signup_data: dict[str, str]):  # noqa
    result = await auth_services.create_user(UserSignUpData(**signup_data), session)  # type: ignore
    assert isinstance(result, UserDB)


async def test_create_user_fails(
    session: AsyncSession, signup_data: dict[str, Any], user: UserDB  # noqa
):  # noqa
    signup_data["email"] = user.email
    with pytest.raises(HTTPException) as err:
        await auth_services.create_user(UserSignUpData(**signup_data), session)

    assert "Email already registered" in str(err.value)


async def test_verify_user_succeeds(user: UserDB, session: AsyncSession):
    verification_data = auth_schemas.UserVerificationModel(
        email=user.email, code="000000"
    )
    redis_manager.cache_json_item(
        f"verification-code-{verification_data.email}", {"code": "000000"}
    )
    user = await auth_services.verify_user(
        verification_data,
        BackgroundTasks(tasks=[]),
        session,
    )
    # test that the flag for verified user is activated


@pytest.mark.parametrize(
    "verification_data,cached_code",
    [
        ({"email": faker.email(), "code": "000000"}, {"code": "000000"}),
        ({"email": faker.email(), "code": "000000"}, {"code": "000001"}),
        ({"email": faker.email(), "code": "000000"}, None),
    ],
)
async def test_verify_user_fails(
    user: UserDB,
    session: AsyncSession,
    verification_data: dict[str, str],
    cached_code: dict[str, str] | None,
):
    data = auth_schemas.UserVerificationModel(**verification_data)
    redis_manager.cache_json_item(
        f"verification-code-{data.email}", cached_code  # type: ignore
    )
    with pytest.raises(HTTPException) as err:
        await auth_services.verify_user(
            data,
            BackgroundTasks(tasks=[]),
            session,
        )

    assert err.value.detail == "Invalid Verification Code"
