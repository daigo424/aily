from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.db.base import Base, utcnow

if TYPE_CHECKING:
    from .event import Event
    from .message import Message
    from .schedule_draft import ScheduleDraft
    from .task import Task


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), default="web", index=True)
    sender: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    messages: Mapped[list[Message]] = relationship(back_populates="chat", cascade="all, delete-orphan")
    schedule_drafts: Mapped[list[ScheduleDraft]] = relationship(back_populates="chat", cascade="all, delete-orphan")
    events: Mapped[list[Event]] = relationship(back_populates="chat", cascade="all, delete-orphan")
    tasks: Mapped[list[Task]] = relationship(back_populates="chat", cascade="all, delete-orphan")
