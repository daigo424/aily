from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from packages.core.config import settings
from packages.core.infrastructure import llm
from packages.core.schemas import BookingExtraction

TZ = ZoneInfo(settings.timezone)


def _format_history(messages: list[BaseMessage]) -> str:
    if not messages:
        return ""
    lines = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            lines.append(f"[ユーザー]: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"[アシスタント]: {msg.content}")
    return "\n".join(lines)


def execute(text: str, history: list[BaseMessage] | None = None) -> dict[str, Any]:
    now_text = datetime.now(tz=TZ).strftime("%Y-%m-%d %H:%M")
    history_section = ""
    if history:
        formatted = _format_history(history)
        if formatted:
            history_section = f"""
過去の会話履歴:
{formatted}

"""

    prompt = f"""
あなたはIT請負開発の相談予約受付AIです。現在日時は {now_text}（{settings.timezone}）です。
相談予約は 1 回 1 時間の枠で受け付けています。
{history_section}
以下のWhatsAppメッセージからユーザーの意図と相談予約情報を抽出し、返答文を生成してください。
過去の会話履歴がある場合は、その文脈を踏まえて解釈してください。

intent の選び方:
- 日付・時間のいずれかが含まれていれば "book_reservation"
- 既存予約の変更なら "update_booking_request"
- 空き確認なら "ask_availability"
- キャンセルなら "cancel_reservation"
- 挨拶・雑談なら "smalltalk"
- それ以外は "unknown"

reserved_date: 相対表現（明日、来週など）は現在日時を基準に YYYY-MM-DD で解釈。
reserved_time: HH:MM 形式。
notes: 相談したい内容・要望・備考があれば。
follow_up_question: 日付・時刻が不足している場合に聞き返す質問文。揃っていれば null。

reply: ユーザーへの返答文。以下のルールで生成すること。
- **必ずユーザーのメッセージと同じ言語で書くこと**（日本語なら日本語、英語なら英語、など）
- intent が "book_reservation" / "update_booking_request" / "ask_availability" で日時が揃っていれば「1 時間枠で予約を承りました。担当者よりご連絡します。」旨を伝える
- 日時が不足していれば follow_up_question と同じ内容
- intent が "cancel_reservation" であればキャンセル受付の旨
- intent が "smalltalk" であれば予約受付サービスの案内
- それ以外はIT開発相談の予約を促す案内

現在のメッセージ:
{text}
"""
    response = llm.client.gen_json(
        prompt=prompt,
        schema=BookingExtraction.model_json_schema(),
        temperature=0.1,
    )
    booking = BookingExtraction.model_validate(response)

    return booking.model_dump(mode="json")
