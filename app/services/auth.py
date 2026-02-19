from datetime import UTC, datetime, timedelta
from random import randint
from typing import Literal, cast

import bcrypt
import jwt
from fastapi import BackgroundTasks, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic.networks import EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import logger
from app.mailer import send_mail
from app.models import User as UserDB
from app.redis_manager import redis_manager
from app.schemas import auth as auth_schema
from app.settings import Settings

settings = Settings()

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM

ACCESS_TOKEN_LIFESPAN = timedelta(days=14)
REFRESH_TOKEN_LIFESPAN = timedelta(days=28)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token")


def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(
        bytes(plain_password, encoding="utf-8"),
        bytes(hashed_password, encoding="utf-8"),
    )


def get_password_hash(password: str):
    return bcrypt.hashpw(
        bytes(password, encoding="utf-8"),
        bcrypt.gensalt(),
    ).decode()


async def get_user(email: EmailStr, session: AsyncSession) -> UserDB | None:
    stmt = select(UserDB).where(UserDB.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    user_data: auth_schema.UserSignUpData,
    session: AsyncSession,
):
    result = await session.execute(
        select(UserDB).where(UserDB.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    new_user = UserDB(
        email=user_data.email,
        password=hashed_password,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def verify_user(
    verification_data: auth_schema.UserVerificationData,
    background_task: BackgroundTasks,
    session: AsyncSession,
):
    """
    Verify the User Against a Token generated and stored in the Sign up Process for the User Credentials
    """
    data = redis_manager.get_json_item(f"verification-code-{verification_data.email}")
    if not isinstance(data, dict):
        logger.error(f"Corrupt Log Data: {data}")
        raise HTTPException(status_code=500, detail="Corrupted Cache Data")
    if not data or data.get("code") != verification_data.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    user = await get_user(verification_data.email, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not Found")

    background_task.add_task(
        send_mail,
        subject="Welcome to {Project Name}",
        receipients=[user.email],
        payload={"name": user.email.split("@")[0]},
        template="auth/welcome.html",
    )
    return await update_user(
        verification_data.email, auth_schema.UpdateUserModel(), session
    )


async def resend_verification_code(
    email: str, session: AsyncSession, background_task: BackgroundTasks
):
    user = await get_user(email, session)
    if not user:
        logger.warning(f"Email Verification Requested for invalid user {email}")
        return {"detail": "Verification code resent"}

    code = str(randint(1000, 9999))
    redis_manager.cache_json_item(
        key=f"verification-code-{email}", value={"code": code}
    )

    first_name = cast(UserDB, user).email.split("@")[0]
    background_task.add_task(
        send_mail,
        subject="OTP Verification",
        receipients=[user.email],
        payload={"name": first_name, "otp": code},
        template="auth/verification.html",
    )

    return {"detail": "Verification code resent"}


async def initiate_password_reset(
    email: str, session: AsyncSession, background_task: BackgroundTasks
):
    user = await get_user(email, session)
    if not user:
        return {"detail": "Password reset code sent"}

    code = str(randint(1000, 9999))
    redis_manager.cache_json_item(
        key=f"reset-code-{email}", value={"code": code, "email": email}, ttl=60 * 30
    )

    background_task.add_task(
        send_mail,
        subject="Password Reset",
        receipients=[user.email],
        payload={"username": user.username.title(), "code": code},
        template="auth/initiate_password_reset.html",
    )

    return {"detail": "Password reset code sent"}


async def verify_reset_password_otp(code: str, email: str, session: AsyncSession):
    data = redis_manager.get_json_item(f"reset-code-{email}")
    if not data or data.get("code") != code:
        raise HTTPException(status_code=400, detail="Invalid Reset Code")

    user = await get_user(email, session)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid Reset Code")

    return {"detail": "Code is Correct"}


async def reset_password(
    reset_data: auth_schema.PasswordResetData, session: AsyncSession
):
    data = redis_manager.get_json_item(f"reset-code-{reset_data.email}")
    if not data or data.get("code") != reset_data.code:
        raise HTTPException(status_code=400, detail="Invalid Reset Code")

    user = await get_user(reset_data.email, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_password = get_password_hash(reset_data.new_password)
    stmt = (
        update(UserDB)
        .where(UserDB.email == reset_data.email)
        .values(password=hashed_password)
        .execution_options(synchronize_session="fetch")
    )

    await session.execute(stmt)
    await session.commit()

    return {"detail": "Password reset successfully"}


async def update_user(
    email: str, update_data: auth_schema.UpdateUserModel, session: AsyncSession
):
    data = update_data.model_dump(exclude_none=True, exclude_unset=True)

    old_password: str | None = data.pop("old_password", None)
    new_password: str | None = data.pop("new_password", None)
    if new_password:
        user = await authenticate_user(
            username=email, password=cast(str, old_password), session=session
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        data.update({"password": get_password_hash(new_password)})

    stmt = (
        update(UserDB)
        .where(UserDB.email == email)
        .values(**data)
        .returning(UserDB)
        .execution_options(synchronize_session="fetch")
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def authenticate_user(
    username: EmailStr | str, password: str, session: AsyncSession
) -> UserDB | Literal[False]:
    user: UserDB | None = await get_user(username, session)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


async def signup_user(
    data: auth_schema.UserSignUpData,
    session: AsyncSession,
    background_task: BackgroundTasks,
):
    user = await create_user(data, session)

    background_task.add_task(
        send_mail,
        subject="Welcome to {{ project_name }}",
        receipients=[user.email],
        payload={"username": user.email.split("@")[0].title()},
        template="auth/welcome.html",
    )
    return user


async def signin_user(data: auth_schema.UserSignInData, session: AsyncSession):
    user = await authenticate_user(
        password=data.password, username=data.email, session=session
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": data.email}, expires_delta=ACCESS_TOKEN_LIFESPAN
    )
    refresh_token = create_refresh_token(
        data={"sub": data.email}, expires_delta=REFRESH_TOKEN_LIFESPAN
    )

    return auth_schema.Token(
        token_type="Bearer",
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=datetime.now() + ACCESS_TOKEN_LIFESPAN,
        refresh_expires_at=datetime.now() + REFRESH_TOKEN_LIFESPAN,
    )


async def refresh_token(
    token_data: auth_schema.RefreshTokenModel, session: AsyncSession
):
    payload = jwt.decode(
        token_data.refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM]
    )
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=400, detail="Missing user ID in token")

    user = await get_user(email, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    new_access_token = create_access_token(data={"sub": email})
    return auth_schema.Token(
        token_type="Bearer",
        access_token=new_access_token,
        refresh_token=token_data.refresh_token,
        access_expires_at=datetime.now() + ACCESS_TOKEN_LIFESPAN,
        # TODO: Implement logic to correctly calculate expiry data of refresh token
    )


async def logout(token: str):
    # Implement logic to blacklist token
    redis_manager.cache_json_item(token, {"timestamp": str(datetime.now())})
    return {"detail": "User Logged Out Successfully"}
