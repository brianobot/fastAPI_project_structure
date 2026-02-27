from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.settings import Settings

settings = Settings()  # type: ignore

# Add Support for Both ASYNC and SYNC Database URLs
# With Async being the center of focus
DATABASE_URL = settings.DATABASE_URL
DATABASE_SYNC_URL = settings.DATABASE_URL.replace("+asyncpg", "")

sync_engine = create_engine(DATABASE_SYNC_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine)

async_engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
