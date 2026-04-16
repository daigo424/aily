from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from packages.core.constants import ConversationIntent


class BookingExtraction(BaseModel):
    intent: Literal[
        ConversationIntent.BOOK_RESERVATION,
        ConversationIntent.UPDATE_BOOKING_REQUEST,
        ConversationIntent.ASK_AVAILABILITY,
        ConversationIntent.CANCEL_RESERVATION,
        ConversationIntent.SMALLTALK,
        ConversationIntent.UNKNOWN,
    ] = Field(default=ConversationIntent.UNKNOWN, description="ユーザーの意図")
    reserved_date: date | None = Field(default=None, description="相談希望日 (YYYY-MM-DD)")
    reserved_time: str | None = Field(default=None, description="相談希望時刻 (HH:MM)")
    notes: str | None = Field(default=None, description="相談内容・要望・備考")
    follow_up_question: str | None = Field(default=None, description="不足情報を聞き返す質問文")
    reply: str = Field(default="", description="ユーザーへの返答文（ユーザーと同じ言語で）")


class NormalizedInbound(BaseModel):
    sender: str
    customer_name: str | None = None
    message_type: Literal["text", "image", "audio", "unknown"]
    text_for_llm: str
    wamid: str | None = None
    media_meta: dict = Field(default_factory=dict)
    raw_payload: dict = Field(default_factory=dict)
