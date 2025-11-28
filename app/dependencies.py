import jwt
from typing import AsyncGenerator, Annotated

from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Depends, status

from app.database import AsyncSessionLocal
from app.models.auth import User as UserDB
from app.redis_manager import redis_manager
from app.schemas import auth as auth_schemas
from app.services import auth as auth_services


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    token: Annotated[str, Depends(auth_services.oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # check if the user token has been added to the list of logged out tokens
    if redis_manager.get_json_item(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or Expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload: dict = jwt.decode(
            token, auth_services.JWT_SECRET, algorithms=[auth_services.JWT_ALGORITHM]
        )
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = auth_schemas.TokenData(username=username)
    except InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
            headers={"WWW-Authenticate": "Bearer"},
        )
    user: UserDB | None = await auth_services.get_user(
        email=token_data.username, session=db
    )
    if not user:
        raise credentials_exception
    return user