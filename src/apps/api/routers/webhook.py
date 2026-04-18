import json

from fastapi import APIRouter, Request, Response
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.db.repositories import Repository
from packages.core.db.session import SessionLocal
from packages.core.graph.state import BookingState
from packages.core.infrastructure import chatapp
from packages.core.logging import logger

from apps.api.common import normalize_message

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    logger.debug("✋ Catch verify_webhook()")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.verify_token:
        return Response(content=challenge or "", media_type="text/plain")
    return Response(content="forbidden", status_code=403)


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict:
    logger.debug("✋ Catch receive_webhook()")
    payload = await request.json()
    logger.debug(json.dumps(payload, ensure_ascii=False, indent=2))

    if payload.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    booking_graph = request.app.state.booking_graph
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

                    saved_message = repo.save_message(
                        conversation=conversation,
                        customer=customer,
                        wamid=wamid,
                        direction="inbound",
                        message_type=normalized["message_type"],
                        text_content=text_body,
                        raw_payload=message,
                        normalized_payload=normalized,
                        raw_llm_result={},
                    )

                    initial_state = BookingState(
                        messages=[HumanMessage(content=text_body or "")],
                        text_body=text_body,
                        sender=sender,
                        customer_id=customer.id,
                        conversation_id=conversation.id,
                        wamid=wamid,
                        raw_message=message,
                        normalized=normalized,
                        pending_cancel_ids=repo.get_cancel_flow_reservation_ids(conversation.id),
                        raw_llm_result={},
                        intent="",
                        reply="...",
                    )
                    result = booking_graph.invoke(
                        initial_state,
                        config={
                            "configurable": {
                                "thread_id": str(conversation.id),
                                "repo": repo,
                                "conversation": conversation,
                                "source_message": saved_message,
                            }
                        },
                    )
                    saved_message.raw_llm_result = result["raw_llm_result"]
                    reply = result["reply"]

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
                        raw_llm_result={},
                    )

        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception(f"Webhook processing failed: {e}", exc_info=True)
    finally:
        db.close()

    return {"status": "ok"}
