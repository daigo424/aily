from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.constants import TaskStatus
from packages.core.db.models import Event, Task
from packages.core.db.repositories import Repository
from packages.core.db.session import get_db

router = APIRouter(prefix="/admin")

_TZ = ZoneInfo(settings.timezone)


def _fmt_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ).isoformat()


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def _event_dict(e: Event) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "starts_at": _fmt_dt(e.starts_at),
        "ends_at": _fmt_dt(e.ends_at),
        "notes": e.notes,
        "created_at": _fmt_dt(e.created_at),
        "updated_at": _fmt_dt(e.updated_at),
    }


@router.get("/events")
def list_events(db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    return {"items": [_event_dict(e) for e in repo.list_events()]}


@router.get("/events/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    event = repo.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_dict(event)


class CreateEventBody(BaseModel):
    title: str
    starts_at: str
    ends_at: str
    notes: str | None = None
    chat_id: int


@router.post("/events")
def create_event(body: CreateEventBody, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    event = repo.create_event(
        chat_id=body.chat_id,
        title=body.title,
        starts_at=_parse_dt(body.starts_at),
        ends_at=_parse_dt(body.ends_at),
        notes=body.notes,
    )
    db.commit()
    return _event_dict(event)


class UpdateEventBody(BaseModel):
    title: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    notes: str | None = None


@router.patch("/events/{event_id}")
def update_event(event_id: int, body: UpdateEventBody, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    kwargs: dict = {}
    if body.title is not None:
        kwargs["title"] = body.title
    if body.starts_at is not None:
        kwargs["starts_at"] = _parse_dt(body.starts_at)
    if body.ends_at is not None:
        kwargs["ends_at"] = _parse_dt(body.ends_at)
    if body.notes is not None:
        kwargs["notes"] = body.notes
    event = repo.update_event(event_id, **kwargs)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.commit()
    return _event_dict(event)


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    if not repo.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def _task_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "starts_at": _fmt_dt(t.starts_at),
        "ends_at": _fmt_dt(t.ends_at),
        "status": t.status,
        "notes": t.notes,
        "created_at": _fmt_dt(t.created_at),
        "updated_at": _fmt_dt(t.updated_at),
    }


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    return {"items": [_task_dict(t) for t in repo.list_tasks()]}


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_dict(task)


class CreateTaskBody(BaseModel):
    title: str
    starts_at: str
    ends_at: str
    status: str = TaskStatus.NOT_STARTED
    notes: str | None = None
    chat_id: int


@router.post("/tasks")
def create_task(body: CreateTaskBody, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    task = repo.create_task(
        chat_id=body.chat_id,
        title=body.title,
        starts_at=_parse_dt(body.starts_at),
        ends_at=_parse_dt(body.ends_at),
        status=body.status,
        notes=body.notes,
    )
    db.commit()
    return _task_dict(task)


class UpdateTaskBody(BaseModel):
    title: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    status: str | None = None
    notes: str | None = None


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, body: UpdateTaskBody, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    kwargs: dict = {}
    if body.title is not None:
        kwargs["title"] = body.title
    if body.starts_at is not None:
        kwargs["starts_at"] = _parse_dt(body.starts_at)
    if body.ends_at is not None:
        kwargs["ends_at"] = _parse_dt(body.ends_at)
    if body.status is not None:
        kwargs["status"] = body.status
    if body.notes is not None:
        kwargs["notes"] = body.notes
    task = repo.update_task(task_id, **kwargs)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.commit()
    return _task_dict(task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    repo = Repository(db)
    if not repo.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    db.commit()
    return {"status": "deleted"}
