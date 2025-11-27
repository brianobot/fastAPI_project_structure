from uuid import UUID
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


class UserSignUpData(BaseModel):
    password: Annotated[str, Field(min_length=8)]
    email: Annotated[EmailStr, Field(max_length=254)]


class UserModel(BaseModel):
    id: UUID

    email: EmailStr
    date_created: datetime
    date_updated: datetime
