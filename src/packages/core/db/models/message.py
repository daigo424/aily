from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.db.base import Base, utcnow

if TYPE_CHECKING:
    from .chat import Chat
    from .message_attachment import MessageAttachment
    from .schedule_draft import ScheduleDraft


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(16))
    message_type: Mapped[str] = mapped_column(String(32))
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chat: Mapped[Chat] = relationship(back_populates="messages")
    schedule_drafts: Mapped[list[ScheduleDraft]] = relationship(back_populates="source_message")
    attachments: Mapped[list[MessageAttachment]] = relationship(back_populates="message", cascade="all, delete-orphan")
