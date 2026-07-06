from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.constants import ScheduleDraftStatus, ScheduleItemType, TaskStatus
from packages.core.db.models import Chat, Event, Message, MessageAttachment, ScheduleDraft, Task

_TZ = ZoneInfo(settings.timezone)


class Repository:
    def __init__(self, db: Session):
        self.db = db

    # --- Chat ---

    def get_chat(self, chat_id: int) -> Chat | None:
        return self.db.query(Chat).filter(Chat.id == chat_id).one_or_none()

    def create_chat(self, *, channel: str = "web", sender: str | None = None) -> Chat:
        chat = Chat(channel=channel, sender=sender, status="active")
        self.db.add(chat)
        self.db.flush()
        return chat

    def list_chats(self, channel: str | None = None) -> list[Chat]:
        q = self.db.query(Chat)
        if channel:
            q = q.filter(Chat.channel == channel)
        return q.order_by(Chat.last_message_at.desc()).all()

    def update_chat_title(self, chat_id: int, title: str) -> None:
        chat = self.get_chat(chat_id)
        if chat:
            chat.title = title
            self.db.flush()

    # --- Message ---

    def save_message(
        self,
        *,
        chat: Chat,
        direction: str,
        message_type: str,
        text_content: str | None = None,
        raw_llm_result: dict,
    ) -> Message:
        msg = Message(
            chat_id=chat.id,
            direction=direction,
            message_type=message_type,
            text_content=text_content,
            raw_llm_result=raw_llm_result,
        )
        self.db.add(msg)
        chat.last_message_at = datetime.now(timezone.utc)
        self.db.flush()
        return msg

    def count_messages(self, chat_id: int) -> int:
        return self.db.query(func.count(Message.id)).filter(Message.chat_id == chat_id).scalar() or 0

    # --- MessageAttachment ---

    def save_attachment(
        self,
        *,
        message_id: int,
        file_name: str,
        storage_key: str,
        mime_type: str,
        file_size: int,
    ) -> MessageAttachment:
        att = MessageAttachment(
            message_id=message_id,
            file_name=file_name,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size=file_size,
        )
        self.db.add(att)
        self.db.flush()
        return att

    def get_attachment(self, attachment_id: int) -> MessageAttachment | None:
        return self.db.query(MessageAttachment).filter(MessageAttachment.id == attachment_id).one_or_none()

    def get_attachment_by_message_id(self, message_id: int) -> MessageAttachment | None:
        return self.db.query(MessageAttachment).filter(MessageAttachment.message_id == message_id).first()

    # --- ScheduleDraft ---

    def create_or_update_schedule_draft(
        self,
        *,
        chat: Chat,
        source_message: Message,
        parsed: dict,
    ) -> ScheduleDraft:
        draft = (
            self.db.query(ScheduleDraft)
            .filter(
                ScheduleDraft.chat_id == chat.id,
                ScheduleDraft.status.in_([ScheduleDraftStatus.COLLECTING, ScheduleDraftStatus.READY]),
            )
            .order_by(ScheduleDraft.id.desc())
            .first()
        )
        if not draft:
            draft = ScheduleDraft(
                chat_id=chat.id,
                source_message_id=source_message.id,
                status=ScheduleDraftStatus.COLLECTING,
            )
            self.db.add(draft)
            self.db.flush()

        if parsed.get("item_type"):
            draft.item_type = parsed["item_type"]
        if parsed.get("title"):
            draft.title = parsed["title"]
        raw_date = parsed.get("scheduled_date")
        if raw_date and isinstance(raw_date, str):
            raw_date = date.fromisoformat(raw_date)
        if raw_date:
            draft.scheduled_date = raw_date
        if parsed.get("start_time"):
            draft.start_time = parsed["start_time"]
        if parsed.get("end_time"):
            draft.end_time = parsed["end_time"]
        if parsed.get("notes"):
            draft.notes = parsed["notes"]
        draft.extracted_entities = parsed

        if draft.item_type and draft.title and draft.scheduled_date and draft.start_time and draft.end_time:
            draft.status = ScheduleDraftStatus.READY
        else:
            draft.status = ScheduleDraftStatus.COLLECTING
        return draft

    def confirm_schedule_from_draft(self, draft: ScheduleDraft) -> Event | Task:
        assert draft.scheduled_date is not None
        assert draft.start_time is not None
        assert draft.end_time is not None

        starts_at = datetime.combine(
            draft.scheduled_date,
            datetime.strptime(draft.start_time, "%H:%M").time(),
            tzinfo=_TZ,
        ).astimezone(timezone.utc)
        ends_at = datetime.combine(
            draft.scheduled_date,
            datetime.strptime(draft.end_time, "%H:%M").time(),
            tzinfo=_TZ,
        ).astimezone(timezone.utc)

        if draft.item_type == ScheduleItemType.TASK:
            item: Event | Task = Task(
                chat_id=draft.chat_id,
                draft_id=draft.id,
                title=draft.title,
                starts_at=starts_at,
                ends_at=ends_at,
                status=TaskStatus.NOT_STARTED,
                notes=draft.notes,
            )
        else:
            item = Event(
                chat_id=draft.chat_id,
                draft_id=draft.id,
                title=draft.title,
                starts_at=starts_at,
                ends_at=ends_at,
                notes=draft.notes,
            )
        self.db.add(item)
        draft.status = ScheduleDraftStatus.CONFIRMED
        self.db.flush()
        return item

    # --- Event CRUD ---

    def list_events(self) -> list[Event]:
        return self.db.query(Event).order_by(Event.starts_at.desc()).all()

    def get_event(self, event_id: int) -> Event | None:
        return self.db.query(Event).filter(Event.id == event_id).one_or_none()

    def create_event(self, *, chat_id: int, title: str, starts_at: datetime, ends_at: datetime, notes: str | None) -> Event:
        event = Event(chat_id=chat_id, title=title, starts_at=starts_at, ends_at=ends_at, notes=notes)
        self.db.add(event)
        self.db.flush()
        return event

    def update_event(self, event_id: int, **kwargs) -> Event | None:
        event = self.get_event(event_id)
        if not event:
            return None
        for k, v in kwargs.items():
            if hasattr(event, k):
                setattr(event, k, v)
        self.db.flush()
        return event

    def delete_event(self, event_id: int) -> bool:
        event = self.get_event(event_id)
        if not event:
            return False
        self.db.delete(event)
        self.db.flush()
        return True

    # --- Task CRUD ---

    def list_tasks(self) -> list[Task]:
        return self.db.query(Task).order_by(Task.starts_at.desc()).all()

    def get_task(self, task_id: int) -> Task | None:
        return self.db.query(Task).filter(Task.id == task_id).one_or_none()

    def create_task(
        self,
        *,
        chat_id: int,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        status: str,
        notes: str | None,
    ) -> Task:
        task = Task(chat_id=chat_id, title=title, starts_at=starts_at, ends_at=ends_at, status=status, notes=notes)
        self.db.add(task)
        self.db.flush()
        return task

    def update_task(self, task_id: int, **kwargs) -> Task | None:
        task = self.get_task(task_id)
        if not task:
            return None
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)
        self.db.flush()
        return task

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        self.db.delete(task)
        self.db.flush()
        return True
