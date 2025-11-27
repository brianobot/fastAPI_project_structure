from typing import Annotated

from pydantic import EmailStr
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Body, BackgroundTasks

from app.dependencies import get_db
from app.schemas import auth as auth_schemas
from app.services import auth as auth_services

router = APIRouter(prefix="/auth", tags=["Authentication"])


EmailBody = Annotated[EmailStr, Body(embed=True)]
DBDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/signup", response_model=auth_schemas.UserModel)
async def signup(
    db: DBDep,
    request_data: auth_schemas.UserSignUpData,
):
    return await auth_services.signup_user(request_data, db)
