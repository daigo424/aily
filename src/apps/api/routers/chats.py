from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, exists
from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.db.models import Chat, Message, MessageAttachment
from packages.core.db.repositories import Repository
from packages.core.db.session import get_db

router = APIRouter()

_TZ = ZoneInfo(settings.timezone)


def _fmt_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ).isoformat()


@router.get("/chats/search")
def search_chats(q: str = "", db: Session = Depends(get_db)) -> dict:
    words = [w for w in q.strip().split() if w]
    if not words:
        return {"items": []}
    query = db.query(Chat).filter(Chat.channel == "web")
    for word in words:
        query = query.filter(exists().where(and_(Message.chat_id == Chat.id, Message.text_content.ilike(f"%{word}%"))))
    chats = query.order_by(Chat.last_message_at.desc()).all()
    return {
        "items": [
            {
                "id": c.id,
                "title": c.title or "新しいチャット",
                "last_message_at": _fmt_dt(c.last_message_at),
            }
            for c in chats
        ]
    }


@router.get("/chats")
def list_chats(db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    chats = repo.list_chats(channel="web")
    return {
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "last_message_at": _fmt_dt(c.last_message_at),
            }
            for c in chats
        ]
    }


@router.post("/chats")
def create_chat(db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    chat = repo.create_chat(channel="web")
    db.commit()
    return {"id": chat.id, "title": chat.title, "last_message_at": _fmt_dt(chat.last_message_at)}


@router.get("/chats/{chat_id}/messages")
def get_chat_messages(chat_id: int, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    chat = repo.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at.asc()).all()
    items = []
    for m in messages:
        att: MessageAttachment | None = repo.get_attachment_by_message_id(m.id)
        items.append(
            {
                "id": m.id,
                "role": "user" if m.direction == "inbound" else "assistant",
                "content": m.text_content or "",
                "message_type": m.message_type,
                "attachment_id": att.id if att else None,
                "attachment_mime_type": att.mime_type if att else None,
                "attachment_url": _attachment_url(att),
                "created_at": _fmt_dt(m.created_at),
            }
        )
    return {"items": items}


def _attachment_url(att: MessageAttachment | None) -> str | None:
    if att is None:
        return None
    if settings.cloudfront_url:
        return f"{settings.cloudfront_url.rstrip('/')}/{att.storage_key}"
    return None
