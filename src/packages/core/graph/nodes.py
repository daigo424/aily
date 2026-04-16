from __future__ import annotations

from typing import cast
from zoneinfo import ZoneInfo

from langgraph.types import RunnableConfig

from packages.core.config import settings
from packages.core.constants import BookingRequestStatus, ConversationIntent
from packages.core.db.models import Conversation, Message
from packages.core.db.repositories import Repository
from packages.core.usecases import extract_booking

from .state import BookingState


def _repo(config: RunnableConfig) -> Repository:
    return cast(Repository, config["configurable"]["repo"])


def _conversation(config: RunnableConfig) -> Conversation:
    return cast(Conversation, config["configurable"]["conversation"])


def _source_message(config: RunnableConfig) -> Message:
    return cast(Message, config["configurable"]["source_message"])


# ---------------------------------------------------------------------------
# Node: LLM extraction
# ---------------------------------------------------------------------------


def llm_extraction_node(state: BookingState, config: RunnableConfig) -> BookingState:
    text_body = state["text_body"]
    if not text_body:
        return {**state, "gemini_result": {}, "intent": ConversationIntent.UNKNOWN}

    gemini_result = extract_booking.execute(text_body)
    intent = gemini_result.get("intent", ConversationIntent.UNKNOWN)

    conversation = _conversation(config)
    conversation.current_intent = intent
    conversation.state = gemini_result

    return {**state, "gemini_result": gemini_result, "intent": intent}


# ---------------------------------------------------------------------------
# Node: cancel flow — numeric selection
# ---------------------------------------------------------------------------


def handle_cancel_selection_node(state: BookingState, config: RunnableConfig) -> BookingState:
    repo = _repo(config)
    conversation = _conversation(config)
    pending_ids = state["pending_cancel_ids"]
    text_body = state["text_body"] or ""

    idx = int(text_body.strip()) - 1
    cancelled = repo.cancel_reservation(pending_ids[idx]) if 0 <= idx < len(pending_ids) else None

    if cancelled:
        tz = ZoneInfo(settings.timezone)
        local_dt = cancelled.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        reply = f"予約 {cancelled.reservation_code}（{local_dt} {settings.timezone}）をキャンセルしました。またのご利用をお待ちしております。"
        conversation.cancel_flow = None
    else:
        reply = f"1 〜 {len(pending_ids)} の番号を入力してください。"

    return {**state, "reply": reply, "pending_cancel_ids": []}


# ---------------------------------------------------------------------------
# Node: cancel intent — show reservation list
# ---------------------------------------------------------------------------


def handle_cancel_intent_node(state: BookingState, config: RunnableConfig) -> BookingState:
    repo = _repo(config)
    conversation = _conversation(config)
    reservations = repo.get_confirmed_reservations_for_customer(state["customer_id"])

    if not reservations:
        conversation.cancel_flow = None
        return {**state, "reply": "現在キャンセルできる予約はありません。", "pending_cancel_ids": []}

    tz = ZoneInfo(settings.timezone)
    lines = ["キャンセルする予約の番号を入力してください：\n"]
    for i, r in enumerate(reservations, start=1):
        local_dt = r.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        lines.append(f"{i}. {r.reservation_code} / {local_dt} {settings.timezone}")

    pending_ids = [r.id for r in reservations]
    conversation.cancel_flow = {"pending_ids": pending_ids}

    return {**state, "reply": "\n".join(lines), "pending_cancel_ids": pending_ids}


# ---------------------------------------------------------------------------
# Node: booking intent — create/update booking request and confirm if ready
# ---------------------------------------------------------------------------


def handle_booking_intent_node(state: BookingState, config: RunnableConfig) -> BookingState:
    repo = _repo(config)
    conversation = _conversation(config)
    conversation.cancel_flow = None

    db = repo.db
    from packages.core.db.models import Customer as CustomerModel

    customer = db.query(CustomerModel).filter(CustomerModel.id == state["customer_id"]).one()
    source_message = _source_message(config)

    booking_request = repo.create_or_update_booking_request(
        conversation=conversation,
        customer=customer,
        source_message=source_message,
        parsed=state["gemini_result"],
    )

    if booking_request.status != BookingRequestStatus.READY:
        return {**state, "reply": state["gemini_result"].get("reply") or "..."}

    reserved_for = repo.build_reserved_for(booking_request)

    if not repo.is_time_slot_available(reserved_for):
        tz = ZoneInfo(settings.timezone)
        local_dt = reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        reply = f"{local_dt}（{settings.timezone}）はすでに予約が入っています。\n別の日時をお知らせください。"
        booking_request.requested_date = None
        booking_request.requested_time = None
        booking_request.status = BookingRequestStatus.COLLECTING
        return {**state, "reply": reply}

    reservation = repo.confirm_reservation_from_booking_request(booking_request)
    tz = ZoneInfo(settings.timezone)
    local_dt = reservation.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    reply = f"1時間枠で予約を承りました。担当者よりご連絡します。\n[{reservation.reservation_code} / {local_dt} {settings.timezone}]"
    return {**state, "reply": reply}


# ---------------------------------------------------------------------------
# Node: other intents (smalltalk, unknown)
# ---------------------------------------------------------------------------


def handle_other_intent_node(state: BookingState, config: RunnableConfig) -> BookingState:
    _conversation(config).cancel_flow = None
    return {**state, "reply": state["gemini_result"].get("reply") or "..."}
