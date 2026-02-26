from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, EmailStr, Field, model_validator


class Token(BaseModel):
    token_type: str
    access_token: str
    refresh_token: str
    access_expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None


class TokenData(BaseModel):
    username: str


class RefreshTokenModel(BaseModel):
    refresh_token: Annotated[str, Field(min_length=32)]


class UserSignUpData(BaseModel):
    password: Annotated[str, Field(min_length=8, max_length=50)]
    email: Annotated[EmailStr, Field(max_length=254), AfterValidator(str.lower)]


class UserVerificationModel(BaseModel):
    email: EmailStr
    code: Annotated[str, Field(min_length=6, max_length=6)]


class PasswordResetData(BaseModel):
    code: str
    email: Annotated[EmailStr, Field(max_length=254), AfterValidator(str.lower)]
    new_password: Annotated[str, Field(min_length=8)]


class UserSignInData(BaseModel):
    email: Annotated[EmailStr, Field(max_length=100), AfterValidator(str.lower)]
    password: Annotated[str, Field(min_length=8)]


class UserModel(BaseModel):
    id: UUID

    email: EmailStr
    date_created: datetime
    date_updated: datetime


class UpdateUserModel(BaseModel):
    old_password: Annotated[str | None, Field(min_length=8)] = None
    new_password: Annotated[str | None, Field(min_length=8)] = None

    @model_validator(mode="after")
    def check_password_dependency(self) -> "UpdateUserModel":
        if self.new_password and not self.old_password:
            raise ValueError("old_password is required if new_password is provided.")
        return self
