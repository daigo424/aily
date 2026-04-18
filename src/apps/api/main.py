import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy.orm import Session

from packages.core.config import settings
from packages.core.db.repositories import Repository
from packages.core.db.session import SessionLocal
from packages.core.graph import build_graph
from packages.core.graph.state import BookingState
from packages.core.infrastructure import chatapp, socket
from packages.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    pool = ConnectionPool(conninfo=settings.cp_conversation_database_url, max_size=10, open=True, kwargs={"autocommit": True, "row_factory": dict_row})
    checkpointer = PostgresSaver(pool)  # type: ignore[arg-type]
    checkpointer.setup()
    app.state.booking_graph = build_graph(checkpointer)
    logger.debug("✅ LangGraph PostgresSaver checkpointer initialized")
    yield
    pool.close()
    logger.debug("✅ LangGraph checkpointer connection pool closed")


app = FastAPI(title="WhatsApp Booking API", lifespan=lifespan)


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
