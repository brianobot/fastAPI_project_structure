from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import dependencies
from app.models import User as UserDB
from app.routers.tests.conftest import access_token  # noqa


async def test_get_db_yields_session():
    """
    Verifies that get_db yields an AsyncSession and cleans up properly.
    """
    generator = dependencies.get_db()

    session = await anext(generator)  # type: ignore

    try:
        assert isinstance(session, AsyncSession)
        assert session.is_active
    finally:
        try:
            await anext(generator)
        except StopAsyncIteration:
            pass


class TestCurrentUserDependency:
    async def test_get_current_user_success(self, access_token, session, user):  # noqa
        # Ensure the user exists in DB and JWT is valid
        user = await dependencies.get_current_user(access_token, session)
        assert isinstance(user, UserDB)
        assert user.email == user.email

    async def test_get_current_user_blacklisted_token(
        self, access_token, session  # noqa
    ):  # noqa
        with patch("app.dependencies.redis_manager.get_json_item") as mock_redis:
            mock_redis.return_value = {"status": "logged_out"}

            with pytest.raises(HTTPException) as exc:
                await dependencies.get_current_user(access_token, session)
            assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid or Expired credentials" in exc.value.detail

    async def test_get_current_user_invalid_token(self, session):
        invalid_token = "not-a-real-token"
        # The jwt.decode will naturally raise InvalidTokenError
        with pytest.raises(HTTPException) as exc:
            await dependencies.get_current_user(invalid_token, session)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_current_user_missing_sub(self, access_token, session):  # noqa
        # Mock decode to return a payload without 'sub'
        with patch("jwt.decode") as mock_decode:
            mock_decode.return_value = {"not_sub": "data"}

            with pytest.raises(HTTPException) as exc:
                await dependencies.get_current_user(access_token, session)
            assert exc.value.detail == "Could not validate credentials"

    async def test_get_current_user_not_in_db(self, access_token, session):  # noqa
        # Mock get_user to return None
        with patch("app.services.auth.get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(HTTPException) as exc:
                await dependencies.get_current_user(access_token, session)
            assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
