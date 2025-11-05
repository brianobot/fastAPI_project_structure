from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
# from app.database import SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # ignore for brevity
    # async with SessionLocal() as session:
    #     yield session
    pass 

