from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.settings import settings

DATABASE_URL = settings.DATABASE_URL

async_engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
