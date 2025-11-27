from typing import TYPE_CHECKING
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy import String, JSON


if TYPE_CHECKING:
    pass

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AbstractBase(DeclarativeBase):
    """
    Base class for all Models, Defines the date_created and date_updated columns
    """

    __abstract__ = True
    id: Mapped[UUID] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        unique=True,
        nullable=False,
        default=uuid.uuid4,
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    date_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(AbstractBase):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password: Mapped[str]
    phone_number: Mapped[str]
    interested_services: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
