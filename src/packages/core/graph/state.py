from typing import Any

from typing_extensions import TypedDict


class BookingState(TypedDict):
    # Per-turn inputs
    text_body: str | None
    sender: str
    customer_id: int
    conversation_id: int
    wamid: str | None
    raw_message: dict[str, Any]
    normalized: dict[str, Any]

    # Persisted cancel flow state (hydrated from conversation.cancel_flow at turn start)
    pending_cancel_ids: list[int]

    # LLM extraction result
    gemini_result: dict[str, Any]
    intent: str

    # Reply to send back to the customer
    reply: str
