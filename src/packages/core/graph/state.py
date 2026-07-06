from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ScheduleState(TypedDict):
    # Messages history — accumulated across turns via checkpointer
    messages: Annotated[list[BaseMessage], add_messages]

    # Per-turn inputs
    text_body: str | None
    sender: str
    chat_id: int
    image_base64: str | None
    image_mime_type: str | None

    # LLM extraction result
    raw_llm_result: dict[str, Any]
    intent: str

    # Reply to send back to the user
    reply: str
