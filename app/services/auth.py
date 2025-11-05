from datetime import timedelta

from fastapi import HTTPException
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import Settings
from app.models import User as UserDB
from app.schemas import auth as auth_schema

settings = Settings()

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM

ACCESS_TOKEN_LIFESPAN = timedelta(days=2)
REFRESH_TOKEN_LIFESPAN = timedelta(days=5)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token")


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    return pwd_context.hash(password)


async def get_user(email: str, session: AsyncSession) -> UserDB | None:
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

    result = await session.execute(
        select(UserDB).where(UserDB.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already used")

    hashed_password = get_password_hash(user_data.password)
    new_user = UserDB(
        email=user_data.email,
        password=hashed_password,
        username=user_data.email,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def signup_user(
    data: auth_schema.UserSignUpData,
    session: AsyncSession,
):
    return await create_user(data, session)


