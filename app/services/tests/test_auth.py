from datetime import timedelta
from typing import Any
from unittest.mock import patch

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


async def test_resend_verification_code_for_user(user: UserDB, session: AsyncSession):
    result = await auth_services.resend_verification_code(
        user.email, session, BackgroundTasks(tasks=[])
    )
    assert result == {"detail": "Verification code resent"}


async def test_resend_verification_code_for_none_user(session: AsyncSession):
    result = await auth_services.resend_verification_code(
        faker.email(), session, BackgroundTasks(tasks=[])
    )
    assert result == {"detail": "Verification code resent"}


async def test_initiate_password_reset_for_user(user: UserDB, session: AsyncSession):
    result = await auth_services.initiate_password_reset(
        user.email, session, BackgroundTasks(tasks=[])
    )
    assert result == {"detail": "Password reset code sent"}


async def test_initiate_password_reset_for_none_user(session: AsyncSession):
    result = await auth_services.initiate_password_reset(
        faker.email(), session, BackgroundTasks(tasks=[])
    )
    assert result == {"detail": "Password reset code sent"}


async def test_verify_reset_password_otp_for_user(user: UserDB, session: AsyncSession):
    code = "000000"
    redis_manager.cache_json_item(f"reset-code-{user.email}", {"code": code})
    result = await auth_services.verify_reset_password_otp(code, user.email, session)
    assert result == {"detail": "Verification is Successful"}


@pytest.mark.parametrize(
    "code",
    [
        "000001",
        "000000",
    ],
)
async def test_verify_reset_password_otp_fails(session: AsyncSession, code: str):
    none_existence_email = faker.email()
    redis_manager.cache_json_item(
        f"reset-code-{none_existence_email}", {"code": "000000"}
    )
    with pytest.raises(HTTPException) as err:
        await auth_services.verify_reset_password_otp(
            code, none_existence_email, session
        )

    assert err.value.detail == "Invalid Reset Code"


async def test_reset_password_for_user(user: UserDB, session: AsyncSession):
    redis_manager.cache_json_item(f"reset-code-{user.email}", {"code": "000000"})
    result = await auth_services.reset_password(
        auth_schemas.PasswordResetData(
            code="000000", email=user.email, new_password="newpassword"
        ),
        session,
    )
    assert result == {"detail": "Password reset successfully"}


@pytest.mark.parametrize(
    "code",
    [
        "000000",
        "000001",
    ],
)
async def test_reset_password_fails(user: UserDB, session: AsyncSession, code: str):
    none_existence_email = faker.email()
    redis_manager.cache_json_item(
        f"reset-code-{none_existence_email}", {"code": "000000"}
    )
    with pytest.raises(HTTPException) as err:
        await auth_services.reset_password(
            auth_schemas.PasswordResetData(
                code=code, email=none_existence_email, new_password="newpassword"
            ),
            session,
        )

    assert err.value.detail == "Invalid Reset Code"


async def test_update_user(user: UserDB, session: AsyncSession):
    updated_user = await auth_services.update_user(
        user.email,
        auth_schemas.UpdateUserModel(
            old_password="password", new_password="new_password"
        ),
        session,
    )
    assert isinstance(updated_user, UserDB)
    assert auth_services.verify_password("new_password", updated_user.password)


async def test_update_user_fails(user: UserDB, session: AsyncSession):
    with pytest.raises(HTTPException) as err:
        await auth_services.update_user(
            user.email,
            auth_schemas.UpdateUserModel(
                old_password="incorrectpassword", new_password="new_password"
            ),
            session,
        )
    assert err.value.detail == "Incorrect Old Password"


@pytest.mark.parametrize(
    "expires_delta",
    [
        None,
        timedelta(days=10),
    ],
)
async def test_create_access_token(expires_delta: timedelta | None):
    auth_services.create_access_token({"sub": faker.email()}, expires_delta)


@pytest.mark.parametrize(
    "expires_delta",
    [
        None,
        timedelta(days=10),
    ],
)
async def test_refresh_access_token(expires_delta: timedelta | None):
    auth_services.create_refresh_token({"sub": faker.email()}, expires_delta)


async def test_authenticate_user(user: UserDB, session: AsyncSession):
    result = await auth_services.authenticate_user(user.email, "password", session)
    assert isinstance(result, UserDB)
    assert result.id == user.id


@pytest.mark.parametrize(
    "email,password",
    [
        (faker.email(), "password"),
        (faker.email(), "incorrectpassword"),
    ],
)
async def test_authenticate_user_returns_none(
    session: AsyncSession, email: str, password: str
):
    result = await auth_services.authenticate_user(email, password, session)
    assert result is False


async def test_signup_user(session: AsyncSession):
    email = faker.email()
    result = await auth_services.signup_user(
        auth_schemas.UserSignUpData(email=email, password="password"),
        session,
        BackgroundTasks(tasks=[]),
    )
    assert isinstance(result, UserDB)
    assert result.email == email


async def test_signin_user(user: UserDB, session: AsyncSession):
    result = await auth_services.signin_user(
        auth_schemas.UserSignInData(email=user.email, password="password"), session
    )
    assert isinstance(result, auth_schemas.Token)


async def test_signin_user_for_none_user(session: AsyncSession):
    with pytest.raises(HTTPException) as err:
        await auth_services.signin_user(
            auth_schemas.UserSignInData(email=faker.email(), password="password"),
            session,
        )

    assert err.value.detail == "Incorrect email or password"


async def test_refresh_token(user: UserDB, session: AsyncSession):
    initial_refresh_token = auth_services.create_refresh_token({"sub": user.email})
    updated_refreshed_token = await auth_services.refresh_token(
        auth_schemas.RefreshTokenModel(refresh_token=initial_refresh_token), session
    )
    assert updated_refreshed_token


@pytest.mark.parametrize(
    "email,error_message",
    [(faker.email(), "Invalid Refresh Token"), (None, "Invalid Refresh Token")],
)
async def test_refresh_token_fails(
    email: str | None, error_message: str, session: AsyncSession
):
    invalid_refresh_token = auth_services.create_refresh_token({"sub": email})  # type: ignore
    with pytest.raises(HTTPException) as err:
        await auth_services.refresh_token(
            auth_schemas.RefreshTokenModel(refresh_token=invalid_refresh_token), session
        )
    assert err.value.detail == error_message


async def test_refresh_token_payload_return_none(session: AsyncSession):
    invalid_refresh_token = auth_services.create_refresh_token({"sub": faker.email()})  # type: ignore
    with patch("app.services.auth.jwt.decode") as mock_decode:
        mock_decode.return_value = None

        with pytest.raises(HTTPException) as err:
            await auth_services.refresh_token(
                auth_schemas.RefreshTokenModel(refresh_token=invalid_refresh_token),
                session,
            )
    assert err.value.detail == "Invalid Refresh Token"
