from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.db.base import Base, utcnow

if TYPE_CHECKING:
    from .booking_request import BookingRequest
    from .conversation import Conversation
    from .message import Message
    from .reservation import Reservation


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    conversations: Mapped[list[Conversation]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    messages: Mapped[list[Message]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    booking_requests: Mapped[list[BookingRequest]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    reservations: Mapped[list[Reservation]] = relationship(back_populates="customer", cascade="all, delete-orphan")
