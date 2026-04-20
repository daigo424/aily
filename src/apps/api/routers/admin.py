from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.constants import ReservationStatus
from packages.core.db.models import BookingRequest, Conversation, Customer, Message, Reservation
from packages.core.db.repositories import Repository
from packages.core.db.session import get_db
from packages.core.infrastructure import chatapp

router = APIRouter(prefix="/admin")

_TZ = ZoneInfo(settings.timezone)


def _fmt_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ).isoformat()


@router.get("/customers")
def list_customers(page: int = 1, per_page: int = 20, db: Session = Depends(get_db)):
    offset = (page - 1) * per_page
    total = (
        db.query(func.count(Customer.id.distinct()))
        .join(Message, Message.customer_id == Customer.id)
        .scalar()
        or 0
    )
    rows = (
        db.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.max(Message.created_at).label("last_message_at"),
            func.count(Conversation.id.distinct()).label("conversation_count"),
        )
        .join(Message, Message.customer_id == Customer.id)
        .join(Conversation, Conversation.customer_id == Customer.id)
        .group_by(Customer.id, Customer.name, Customer.phone)
        .order_by(func.max(Message.created_at).desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "phone": r.phone,
                "last_message_at": _fmt_dt(r.last_message_at),
                "conversation_count": r.conversation_count,
            }
            for r in rows
        ],
    }


@router.get("/customers/{phone}")
def get_customer(phone: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.phone == phone).one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"id": customer.id, "phone": customer.phone, "name": customer.name}


@router.get("/customers/{phone}/messages")
def list_customer_messages(phone: str, page: int = 0, per_page: int = 50, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.phone == phone).one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    limit = (page + 1) * per_page
    msgs = (
        db.query(Message)
        .filter(Message.customer_id == customer.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": m.id,
                "direction": m.direction,
                "message_type": m.message_type,
                "text_content": m.text_content,
                "created_at": _fmt_dt(m.created_at),
            }
            for m in msgs
        ],
        "has_more": len(msgs) == limit,
    }


class SendMessageBody(BaseModel):
    text: str


@router.post("/customers/{phone}/messages")
def send_customer_message(phone: str, body: SendMessageBody):
    chatapp.client.send_text_message(phone, body.text)
    return {"status": "ok"}


@router.get("/reservations")
def list_reservations(
    show_completed: bool = False,
    show_voided: bool = False,
    show_cancelled: bool = False,
    db: Session = Depends(get_db),
):
    excluded = []
    if not show_completed:
        excluded.append(ReservationStatus.COMPLETED)
    if not show_voided:
        excluded.append(ReservationStatus.VOIDED)
    if not show_cancelled:
        excluded.append(ReservationStatus.CANCELLED)

    q = db.query(Reservation, Customer).join(Customer, Customer.id == Reservation.customer_id)
    if excluded:
        q = q.filter(~Reservation.status.in_(excluded))
    rows = q.order_by(Reservation.reserved_for.desc()).all()

    return {
        "items": [
            {
                "id": r.id,
                "reservation_code": r.reservation_code,
                "status": r.status,
                "reserved_for": _fmt_dt(r.reserved_for),
                "completed_at": _fmt_dt(r.completed_at),
                "voided_at": _fmt_dt(r.voided_at),
                "cancelled_at": _fmt_dt(r.cancelled_at),
                "customer_name": c.name,
                "phone": c.phone,
            }
            for r, c in rows
        ]
    }


@router.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(Reservation, Customer, BookingRequest)
        .join(Customer, Customer.id == Reservation.customer_id)
        .outerjoin(BookingRequest, BookingRequest.id == Reservation.booking_request_id)
        .filter(Reservation.id == reservation_id)
        .one_or_none()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    r, c, br = row
    return {
        "id": r.id,
        "reservation_code": r.reservation_code,
        "status": r.status,
        "reserved_for": _fmt_dt(r.reserved_for),
        "completed_at": _fmt_dt(r.completed_at),
        "voided_at": _fmt_dt(r.voided_at),
        "cancelled_at": _fmt_dt(r.cancelled_at),
        "notes": r.notes,
        "created_at": _fmt_dt(r.created_at),
        "updated_at": _fmt_dt(r.updated_at),
        "customer_id": c.id,
        "customer_name": c.name,
        "phone": c.phone,
        "booking_request_id": br.id if br else None,
        "booking_request_status": br.status if br else None,
        "extracted_entities": br.extracted_entities if br else None,
    }


class UpdateStatusBody(BaseModel):
    status: ReservationStatus


@router.patch("/reservations/{reservation_id}/status")
def update_reservation_status(reservation_id: int, body: UpdateStatusBody, db: Session = Depends(get_db)):
    repo = Repository(db)
    reservation = repo.update_reservation_status(reservation_id, body.status)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found or already cancelled")
    db.commit()
    return {"status": reservation.status}
