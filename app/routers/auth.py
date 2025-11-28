from typing import Annotated

from fastapi.routing import APIRouter
from pydantic import EmailStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends, status, Body, BackgroundTasks, HTTPException

from app.dependencies import get_db
from app.models import User as UserDB
from app.schemas import auth as auth_schemas
from app.dependencies import get_current_user
from app.services import auth as auth_services
from app.settings import Settings

settings = Settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Declare Depends for better reusuabilty
DBDep = Annotated[AsyncSession, Depends(get_db)]
EmailBody = Annotated[EmailStr, Body(embed=True)]
CurrentUserDep = Annotated[UserDB, Depends(get_current_user)]


@router.post("/signup", response_model=auth_schemas.UserModel) 
async def signup(
    db: DBDep,
    bg_task: BackgroundTasks, # needed to send verification/welcome email
    request_data: auth_schemas.UserSignUpData,
):
    return await auth_services.signup_user(request_data, db, bg_task)


@router.post("/initiate_password_reset")
async def initiate_password_reset(
    db: DBDep,
    email: EmailBody,
    background_task: BackgroundTasks,
):
    return await auth_services.initiate_password_reset(email, db, background_task)


@router.post("/verify_password_reset")
async def verify_reset_password_otp(
    db: DBDep, code: Annotated[str, Body(embed=True)], email: EmailBody
):
    return await auth_services.verify_reset_password_otp(code, email, db)


@router.post("/reset_password")
async def reset_password(
    db: DBDep,
    reset_data: auth_schemas.PasswordResetData,
):
    return await auth_services.reset_password(reset_data, db)


@router.post("/token", response_model=auth_schemas.Token)
async def signin(db: DBDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    try:
        login_data = auth_schemas.UserSignInData.model_validate(
            {"email": form_data.username, "password": form_data.password}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors(),  # preserves Pydantic-style error format
        )
    return await auth_services.signin_user(login_data, db)


@router.post("/logout")
async def logout(
    _: CurrentUserDep,
    token: Annotated[str, Depends(auth_services.oauth2_scheme)]
):
    return await auth_services.logout(token)


@router.post("/refresh_token")
async def get_refresh_token(
    db: DBDep,
    token_data: auth_schemas.RefreshTokenModel,
):
    return await auth_services.refresh_token(token_data, db)


@router.get("/me", response_model=auth_schemas.UserModel)
async def get_user_detail(user: CurrentUserDep):
    return user


@router.patch(
    "/me", response_model=auth_schemas.UserModel, status_code=status.HTTP_202_ACCEPTED
)
async def update_user_detail(
    db: DBDep,
    user: CurrentUserDep,
    update_data: auth_schemas.UpdateUserModel,
):
    return await auth_services.update_user(user.email, update_data, db)

