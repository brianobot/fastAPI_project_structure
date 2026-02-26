import typing
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.dependencies import get_db
from app.main import app
from app.models._base import AbstractBase
from app.settings import Settings

if typing.TYPE_CHECKING:
    pass


settings = Settings()  # type: ignore

# Uses an SQLITE In-memory DB for setting
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def run_migrations():
    await setup_db()


@pytest.fixture(scope="session", autouse=True)
def mock_fastmail_send():
    """
    Globally patches FastMail.send_message for the entire test session.
    """
    # Use the string path to where FastMail is imported in your app
    with patch("app.mailer.FastMail.send_message", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
async def client():
    base_url = "http://test"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=base_url) as client:
        yield client


@pytest.fixture
async def session():
    async for session_obj in override_get_db():
        yield session_obj


@pytest.fixture
async def user(session: AsyncSession):
    from app.models.tests.factories import UserFactory

    user = UserFactory.build()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def setup_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(AbstractBase.metadata.drop_all)
        await conn.run_sync(AbstractBase.metadata.create_all)
