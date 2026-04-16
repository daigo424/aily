from enum import StrEnum


class ReservationStatus(StrEnum):
    PENDING = "pending"  # 予約受付済・確認中
    COMPLETED = "completed"
    VOIDED = "voided"  # 管理者による無効化
    CANCELLED = "cancelled"  # 顧客によるキャンセル（WhatsApp）


class BookingRequestStatus(StrEnum):
    COLLECTING = "collecting"
    READY = "ready"
    CONFIRMED = "confirmed"


class ConversationIntent(StrEnum):
    BOOK_RESERVATION = "book_reservation"
    UPDATE_BOOKING_REQUEST = "update_booking_request"
    ASK_AVAILABILITY = "ask_availability"
    CANCEL_RESERVATION = "cancel_reservation"
    SMALLTALK = "smalltalk"
    UNKNOWN = "unknown"
