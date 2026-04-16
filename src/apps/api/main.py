import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Response
from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.constants import BookingRequestStatus, ConversationIntent
from packages.core.db.base import Base
from packages.core.db.repositories import Repository
from packages.core.db.session import SessionLocal, engine
from packages.core.infrastructure import chatapp, socket
from packages.core.logging import logger
from packages.core.usecases import extract_booking

Base.metadata.create_all(bind=engine)

app = FastAPI(title="WhatsApp Booking API")


def normalize_message(message: dict) -> dict:
    msg_type = message.get("type", "unknown")
    normalized = {
        "message_type": msg_type,
        "text": None,
        "image": None,
        "audio": None,
        "interactive": None,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    if msg_type == "text":
        normalized["text"] = message.get("text", {}).get("body")
    elif msg_type == "image":
        normalized["image"] = message.get("image", {})
    elif msg_type == "audio":
        normalized["audio"] = message.get("audio", {})
    elif msg_type == "interactive":
        normalized["interactive"] = message.get("interactive", {})
    return normalized


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    logger.debug("✋ Catch verify_webhook()")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.verify_token:
        return Response(content=challenge or "", media_type="text/plain")
    return Response(content="forbidden", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request) -> dict:
    logger.debug("✋ Catch receive_webhook()")
    payload = await request.json()
    logger.debug(json.dumps(payload, ensure_ascii=False, indent=2))

    if payload.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    db: Session = SessionLocal()
    repo = Repository(db)

    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                for status in value.get("statuses", []):
                    logger.debug(f"status event: {status}")

                contacts = value.get("contacts", [])
                customer_name = None
                if contacts:
                    customer_name = contacts[0].get("profile", {}).get("name") or None

                for message in value.get("messages", []):
                    sender = message.get("from")
                    wamid = message.get("id")
                    if not sender:
                        continue
                    if repo.message_exists(wamid):
                        continue

                    customer = repo.get_or_create_customer(phone=sender, name=customer_name)
                    conversation = repo.get_or_create_active_conversation(customer)
                    normalized = normalize_message(message)
                    text_body = normalized.get("text")

                    gemini_result = {}
                    reply = "..."

                    # --- キャンセル選択待ち状態の処理 ---
                    cancel_flow = conversation.cancel_flow or {}
                    pending_ids = cancel_flow.get("pending_ids", [])

                    if pending_ids and text_body and text_body.strip().isdigit():
                        idx = int(text_body.strip()) - 1
                        if 0 <= idx < len(pending_ids):
                            cancelled = repo.cancel_reservation(pending_ids[idx])
                        else:
                            cancelled = None

                        if cancelled:
                            tz = ZoneInfo(settings.timezone)
                            local_dt = cancelled.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                            reply = f"予約 {cancelled.reservation_code}（{local_dt} {settings.timezone}）をキャンセルしました。またのご利用をお待ちしております。"
                            conversation.cancel_flow = None
                        else:
                            reply = f"1 〜 {len(pending_ids)} の番号を入力してください。"

                    else:
                        # --- 通常の LLM 処理 ---
                        if text_body:
                            gemini_result = extract_booking.execute(text_body)
                            intent = gemini_result.get("intent", ConversationIntent.UNKNOWN)
                            conversation.current_intent = intent
                            conversation.state = gemini_result

                            if intent == ConversationIntent.CANCEL_RESERVATION:
                                reservations = repo.get_confirmed_reservations_for_customer(customer.id)
                                if not reservations:
                                    reply = "現在キャンセルできる予約はありません。"
                                    conversation.cancel_flow = None
                                else:
                                    tz = ZoneInfo(settings.timezone)
                                    lines = ["キャンセルする予約の番号を入力してください：\n"]
                                    for i, r in enumerate(reservations, start=1):
                                        local_dt = r.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                                        lines.append(f"{i}. {r.reservation_code} / {local_dt} {settings.timezone}")
                                    reply = "\n".join(lines)
                                    conversation.cancel_flow = {"pending_ids": [r.id for r in reservations]}

                            elif intent in {
                                ConversationIntent.BOOK_RESERVATION,
                                ConversationIntent.UPDATE_BOOKING_REQUEST,
                                ConversationIntent.ASK_AVAILABILITY,
                            }:
                                conversation.cancel_flow = None
                            else:
                                conversation.cancel_flow = None

                    saved_message = repo.save_message(
                        conversation=conversation,
                        customer=customer,
                        wamid=wamid,
                        direction="inbound",
                        message_type=normalized["message_type"],
                        text_content=text_body,
                        raw_payload=message,
                        normalized_payload=normalized,
                        gemini_result=gemini_result,
                    )

                    if text_body and not (pending_ids and text_body.strip().isdigit()):
                        intent = gemini_result.get("intent", ConversationIntent.UNKNOWN)
                        if intent in {
                            ConversationIntent.BOOK_RESERVATION,
                            ConversationIntent.UPDATE_BOOKING_REQUEST,
                            ConversationIntent.ASK_AVAILABILITY,
                        }:
                            booking_request = repo.create_or_update_booking_request(
                                conversation=conversation,
                                customer=customer,
                                source_message=saved_message,
                                parsed=gemini_result,
                            )
                            if booking_request.status == BookingRequestStatus.READY:
                                reserved_for = repo.build_reserved_for(booking_request)
                                if not repo.is_time_slot_available(reserved_for):
                                    tz = ZoneInfo(settings.timezone)
                                    local_dt = reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                                    reply = f"{local_dt}（{settings.timezone}）はすでに予約が入っています。\n別の日時をお知らせください。"
                                    booking_request.requested_date = None
                                    booking_request.requested_time = None
                                    booking_request.status = BookingRequestStatus.COLLECTING
                                else:
                                    reservation = repo.confirm_reservation_from_booking_request(booking_request)
                                    tz = ZoneInfo(settings.timezone)
                                    local_dt = reservation.reserved_for.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                                    reply = (
                                        f"1時間枠で予約を承りました。担当者よりご連絡します。\n"
                                        f"[{reservation.reservation_code} / {local_dt} {settings.timezone}]"
                                    )
                            else:
                                reply = gemini_result.get("reply") or "..."
                        elif intent != ConversationIntent.CANCEL_RESERVATION:
                            reply = gemini_result.get("reply") or "..."

                    chatapp.client.send_text_message(sender, reply)
                    repo.save_message(
                        conversation=conversation,
                        customer=customer,
                        wamid=None,
                        direction="outbound",
                        message_type="text",
                        text_content=reply,
                        raw_payload={"generated": True},
                        normalized_payload={"text": reply},
                        gemini_result={},
                    )

        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception(f"Webhook processing failed: {e}", exc_info=True)
    finally:
        db.close()

    return {"status": "ok"}


if settings.app_env == "local":
    is_debug = False
    try:
        import pydevd_pycharm

        try:
            if socket.is_debug_server_ready("host.docker.internal", 12345):
                pydevd_pycharm.settrace("host.docker.internal", port=12345, stdout_to_server=True, stderr_to_server=True, suspend=False)
                is_debug = True
        except (ConnectionRefusedError, TimeoutError, Exception):
            logger.debug("⚠️　デバッグサーバーに接続できませんでした（スキップします）")
    except ImportError:
        logger.debug("pydevd_pycharm がインストールされていません")
    finally:
        if is_debug:
            logger.debug("🐛　------ Start Debugging ------")
        else:
            logger.debug("🦶　------ Start ------")
