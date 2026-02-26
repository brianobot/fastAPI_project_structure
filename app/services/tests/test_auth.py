from faker import Faker
from fastapi import BackgroundTasks
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


async def test_verify_user(user: UserDB, session: AsyncSession):
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
