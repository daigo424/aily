from __future__ import annotations

from typing import cast
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage
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


def llm_extraction_node(state: BookingState, config: RunnableConfig) -> dict:
    text_body = state["text_body"]
    if not text_body:
        return {"raw_llm_result": {}, "intent": ConversationIntent.UNKNOWN}

    # state["messages"] には今回の HumanMessage がすでに含まれているため、
    # それより前のメッセージを履歴として渡す（指定件数以下で）
    prior_messages = state.get("messages", [])[:-1][-5:]
    raw_llm_result = extract_booking.execute(text_body, history=prior_messages)
    intent = raw_llm_result.get("intent", ConversationIntent.UNKNOWN)

    conversation = _conversation(config)
    conversation.current_intent = intent

    return {"raw_llm_result": raw_llm_result, "intent": intent}


# ---------------------------------------------------------------------------
# Node: cancel flow — numeric selection
# ---------------------------------------------------------------------------


def handle_cancel_selection_node(state: BookingState, config: RunnableConfig) -> dict:
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
        repo.clear_cancel_flow(conversation)
    else:
        reply = f"1 〜 {len(pending_ids)} の番号を入力してください。"

    return {
        "reply": reply,
        "pending_cancel_ids": [],
        "messages": [AIMessage(content=reply)],
    }


# ---------------------------------------------------------------------------
# Node: cancel intent — show reservation list
# ---------------------------------------------------------------------------


def handle_cancel_intent_node(state: BookingState, config: RunnableConfig) -> dict:
    repo = _repo(config)
    conversation = _conversation(config)
    reservations = repo.get_confirmed_reservations_for_customer(state["customer_id"])

    if not reservations:
        repo.clear_cancel_flow(conversation)
        reply = "現在キャンセルできる予約はありません。"
        return {
            "reply": reply,
            "pending_cancel_ids": [],
            "messages": [AIMessage(content=reply)],
        }

    tz = ZoneInfo(settings.timezone)
    lines = ["キャンセルする予約の番号を入力してください：\n"]
    for i, r in enumerate(reservations, start=1):
        local_dt = r.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        lines.append(f"{i}. {r.reservation_code} / {local_dt} {settings.timezone}")

    pending_ids = [r.id for r in reservations]
    repo.set_cancel_flow(conversation, pending_ids)
    reply = "\n".join(lines)

    return {
        "reply": reply,
        "pending_cancel_ids": pending_ids,
        "messages": [AIMessage(content=reply)],
    }


# ---------------------------------------------------------------------------
# Node: availability inquiry — return available dates in requested period
# ---------------------------------------------------------------------------


def handle_availability_node(state: BookingState, config: RunnableConfig) -> dict:
    repo = _repo(config)
    raw = state["raw_llm_result"]
    period = raw.get("availability_period")
    preferred_weekday: int | None = raw.get("preferred_weekday")

    if not period:
        reply = raw.get("reply") or "ご希望の時期を教えていただけますでしょうか？"
        return {"reply": reply, "messages": [AIMessage(content=reply)]}

    try:
        year, month = map(int, period.split("-"))
    except (ValueError, AttributeError):
        reply = raw.get("reply") or "ご希望の時期を教えていただけますでしょうか？"
        return {"reply": reply, "messages": [AIMessage(content=reply)]}

    available_dates = repo.get_available_dates_in_month(year, month, weekday=preferred_weekday)

    if not available_dates:
        reply = f"{year}年{month}月は満席です。別の月をご指定ください。"
        return {"reply": reply, "messages": [AIMessage(content=reply)]}

    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
    lines = [f"{year}年{month}月の予約可能な日程です：\n"]
    for d in available_dates:
        dow = weekday_ja[d.weekday()]
        lines.append(f"・{d.month}/{d.day}（{dow}）")
    lines.append("\nご希望の日付と時間帯を教えてください。")
    reply = "\n".join(lines)
    return {"reply": reply, "messages": [AIMessage(content=reply)]}


# ---------------------------------------------------------------------------
# Node: booking intent — create/update booking request and confirm if ready
# ---------------------------------------------------------------------------


def handle_booking_intent_node(state: BookingState, config: RunnableConfig) -> dict:
    repo = _repo(config)
    conversation = _conversation(config)
    repo.clear_cancel_flow(conversation)

    db = repo.db
    from packages.core.db.models import Customer as CustomerModel

    customer = db.query(CustomerModel).filter(CustomerModel.id == state["customer_id"]).one()
    source_message = _source_message(config)

    booking_request = repo.create_or_update_booking_request(
        conversation=conversation,
        customer=customer,
        source_message=source_message,
        parsed=state["raw_llm_result"],
    )

    if booking_request.status != BookingRequestStatus.READY:
        reply = state["raw_llm_result"].get("reply") or "..."
        return {"reply": reply, "messages": [AIMessage(content=reply)]}

    reserved_for = repo.build_reserved_for(booking_request)

    if not repo.is_time_slot_available(reserved_for):
        tz = ZoneInfo(settings.timezone)
        local_dt = reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        reply = f"{local_dt}（{settings.timezone}）はすでに予約が入っています。\n別の日時をお知らせください。"
        booking_request.requested_date = None
        booking_request.requested_time = None
        booking_request.status = BookingRequestStatus.COLLECTING
        return {"reply": reply, "messages": [AIMessage(content=reply)]}

    reservation = repo.confirm_reservation_from_booking_request(booking_request)
    tz = ZoneInfo(settings.timezone)
    local_dt = reservation.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    reply = f"1時間枠で予約を承りました。担当者よりご連絡します。\n[{reservation.reservation_code} / {local_dt} {settings.timezone}]"
    return {"reply": reply, "messages": [AIMessage(content=reply)]}


# ---------------------------------------------------------------------------
# Node: other intents (smalltalk, unknown)
# ---------------------------------------------------------------------------


def handle_other_intent_node(state: BookingState, config: RunnableConfig) -> dict:
    _repo(config).clear_cancel_flow(_conversation(config))
    reply = state["raw_llm_result"].get("reply") or "..."
    return {"reply": reply, "messages": [AIMessage(content=reply)]}
