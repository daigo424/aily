import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from packages.core.db.repositories import Repository
from packages.core.db.session import SessionLocal
from packages.core.graph.state import BookingState
from packages.core.logging import logger

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    async def generate() -> AsyncGenerator[str, None]:
        db: Session = SessionLocal()
        repo = Repository(db)
        try:
            phone = f"chat_{body.session_id}"
            customer = repo.get_or_create_customer(phone=phone)
            conversation = repo.get_or_create_active_conversation(customer)
            pending_ids = repo.get_cancel_flow_reservation_ids(conversation.id)

            saved_message = repo.save_message(
                conversation=conversation,
                customer=customer,
                wamid=None,
                direction="inbound",
                message_type="text",
                text_content=body.message,
                raw_payload={"text": {"body": body.message}},
                normalized_payload={"message_type": "text", "text": body.message, "received_at": datetime.now(timezone.utc).isoformat()},
                raw_llm_result={},
            )
            db.flush()

            initial_state = BookingState(
                messages=[HumanMessage(content=body.message)],
                text_body=body.message,
                sender=phone,
                customer_id=customer.id,
                conversation_id=conversation.id,
                wamid=None,
                raw_message={"text": {"body": body.message}},
                normalized={"message_type": "text", "text": body.message},
                pending_cancel_ids=pending_ids,
                raw_llm_result={},
                intent="",
                reply="...",
            )

            booking_graph = request.app.state.booking_graph
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: booking_graph.invoke(
                    initial_state,
                    config={
                        "configurable": {
                            "thread_id": str(conversation.id),
                            "repo": repo,
                            "conversation": conversation,
                            "source_message": saved_message,
                        }
                    },
                ),
            )

            saved_message.raw_llm_result = result["raw_llm_result"]
            reply: str = result["reply"]

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

            for word in reply.split(" "):
                yield f"data: {json.dumps(word + ' ')}\n\n"
                await asyncio.sleep(0.04)
            yield "data: [DONE]\n\n"

        except Exception as e:
            db.rollback()
            logger.exception(f"Chat failed: {e}")
            yield f"data: {json.dumps('エラーが発生しました。')}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
