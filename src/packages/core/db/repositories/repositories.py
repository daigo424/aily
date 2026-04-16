from __future__ import annotations

import random
import string
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.constants import BookingRequestStatus, ReservationStatus
from packages.core.db.models import BookingRequest, Conversation, Customer, Message, Reservation

_TZ = ZoneInfo(settings.timezone)


class Repository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_customer(self, phone: str, name: str | None = None) -> Customer:
        customer = self.db.query(Customer).filter(Customer.phone == phone).one_or_none()
        if customer:
            if name and customer.name != name:
                customer.name = name
            return customer
        customer = Customer(phone=phone, name=name)
        self.db.add(customer)
        self.db.flush()
        return customer

    def get_or_create_active_conversation(self, customer: Customer) -> Conversation:
        conversation = (
            self.db.query(Conversation).filter(Conversation.customer_id == customer.id, Conversation.status == "active").order_by(Conversation.id.desc()).first()
        )
        if conversation:
            conversation.last_message_at = datetime.now(timezone.utc)
            return conversation
        conversation = Conversation(customer_id=customer.id, channel="whatsapp", status="active")
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def message_exists(self, wamid: str | None) -> bool:
        if not wamid:
            return False
        return self.db.query(Message).filter(Message.wamid == wamid).first() is not None

    def save_message(
        self,
        *,
        conversation: Conversation,
        customer: Customer,
        wamid: str | None,
        direction: str,
        message_type: str,
        text_content: str | None,
        raw_payload: dict,
        normalized_payload: dict,
        gemini_result: dict,
    ) -> Message:
        msg = Message(
            conversation_id=conversation.id,
            customer_id=customer.id,
            wamid=wamid,
            direction=direction,
            message_type=message_type,
            text_content=text_content,
            raw_payload=raw_payload,
            normalized_payload=normalized_payload,
            gemini_result=gemini_result,
        )
        self.db.add(msg)
        self.db.flush()
        return msg

    def create_or_update_booking_request(
        self,
        *,
        conversation: Conversation,
        customer: Customer,
        source_message: Message,
        parsed: dict,
    ) -> BookingRequest:
        booking_request = (
            self.db.query(BookingRequest)
            .filter(
                BookingRequest.conversation_id == conversation.id,
                BookingRequest.status.in_([BookingRequestStatus.COLLECTING, BookingRequestStatus.READY]),
            )
            .order_by(BookingRequest.id.desc())
            .first()
        )
        if not booking_request:
            booking_request = BookingRequest(
                conversation_id=conversation.id,
                customer_id=customer.id,
                status=BookingRequestStatus.COLLECTING,
                source_message_id=source_message.id,
            )
            self.db.add(booking_request)
            self.db.flush()

        raw_date = parsed.get("reserved_date")
        if raw_date and isinstance(raw_date, str):
            raw_date = date.fromisoformat(raw_date)
        booking_request.requested_date = raw_date or booking_request.requested_date
        booking_request.requested_time = parsed.get("reserved_time") or booking_request.requested_time
        booking_request.notes = parsed.get("notes") or booking_request.notes
        booking_request.extracted_entities = parsed

        if booking_request.requested_date and booking_request.requested_time:
            booking_request.status = BookingRequestStatus.READY
        else:
            booking_request.status = BookingRequestStatus.COLLECTING
        return booking_request

    def is_time_slot_available(self, reserved_for: datetime) -> bool:
        """reserved_for から 1 時間枠が他の confirmed 予約と重複していなければ True"""
        slot_duration = timedelta(hours=1)
        conflicting = (
            self.db.query(Reservation)
            .filter(
                Reservation.status == ReservationStatus.PENDING,
                Reservation.reserved_for < reserved_for + slot_duration,
                Reservation.reserved_for > reserved_for - slot_duration,
            )
            .first()
        )
        return conflicting is None

    @staticmethod
    def build_reserved_for(booking_request: BookingRequest) -> datetime:
        assert booking_request.requested_date is not None
        assert booking_request.requested_time is not None
        reserved_local = datetime.combine(
            booking_request.requested_date,
            time.fromisoformat(booking_request.requested_time),
            tzinfo=_TZ,
        )
        return reserved_local.astimezone(timezone.utc)

    def confirm_reservation_from_booking_request(self, booking_request: BookingRequest) -> Reservation:
        reserved_for = self.build_reserved_for(booking_request)
        reservation = Reservation(
            conversation_id=booking_request.conversation_id,
            customer_id=booking_request.customer_id,
            booking_request_id=booking_request.id,
            reservation_code=self._reservation_code(),
            status=ReservationStatus.PENDING,
            reserved_for=reserved_for,
            notes=booking_request.notes,
        )
        self.db.add(reservation)
        booking_request.status = BookingRequestStatus.CONFIRMED
        self.db.flush()
        return reservation

    def update_reservation_status(self, reservation_id: int, status: ReservationStatus) -> Reservation | None:
        reservation = self.db.query(Reservation).filter(Reservation.id == reservation_id).one_or_none()
        if reservation and reservation.status != ReservationStatus.CANCELLED:
            reservation.status = status
            if status == ReservationStatus.VOIDED:
                reservation.voided_at = datetime.now(timezone.utc)
            elif status == ReservationStatus.COMPLETED:
                reservation.completed_at = datetime.now(timezone.utc)
            self.db.flush()
        return reservation

    def get_confirmed_reservations_for_customer(self, customer_id: int) -> list[Reservation]:
        return (
            self.db.query(Reservation)
            .filter(Reservation.customer_id == customer_id, Reservation.status == ReservationStatus.PENDING)
            .order_by(Reservation.reserved_for.asc())
            .all()
        )

    def cancel_reservation(self, reservation_id: int) -> Reservation | None:
        reservation = self.db.query(Reservation).filter(Reservation.id == reservation_id).one_or_none()
        if reservation and reservation.status == ReservationStatus.PENDING:
            reservation.status = ReservationStatus.CANCELLED
            reservation.cancelled_at = datetime.now(timezone.utc)
            self.db.flush()
        return reservation

    @staticmethod
    def _reservation_code() -> str:
        return "RSV-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
