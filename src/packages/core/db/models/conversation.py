from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.db.base import Base, utcnow

from .customer import Customer
from .message import Message

if TYPE_CHECKING:
    from .booking_request import BookingRequest
    from .reservation import Reservation


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="whatsapp")
    status: Mapped[str] = mapped_column(String(32), default="active")
    current_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    cancel_flow: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    booking_requests: Mapped[list[BookingRequest]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    reservations: Mapped[list[Reservation]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
