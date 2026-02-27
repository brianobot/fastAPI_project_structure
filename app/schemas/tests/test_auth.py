import pytest
from pydantic import ValidationError

from app.schemas import auth as auth_schemas


def test_update_user_model_succeeds():
    auth_schemas.UpdateUserModel(
        old_password="password",
        new_password="newpassword",
    )


def test_update_user_model_fails():
    with pytest.raises(ValidationError) as err:
        auth_schemas.UpdateUserModel(
            new_password="newpassword",
        )

    assert "old_password is required if new_password is provided." in str(
        err.value.errors()
    )
