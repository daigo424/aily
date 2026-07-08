from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from packages.core.constants import ConversationIntent, ScheduleItemType


class ScheduleExtraction(BaseModel):
    intent: Literal[
        ConversationIntent.ADD_SCHEDULE,
        ConversationIntent.LIST_SCHEDULE,
        ConversationIntent.SMALLTALK,
        ConversationIntent.UNKNOWN,
    ] = Field(default=ConversationIntent.UNKNOWN, description="ユーザーの意図")
    item_type: Literal[ScheduleItemType.EVENT, ScheduleItemType.TASK] | None = Field(default=None, description="予定 or タスク")
    title: str | None = Field(default=None, description="予定またはタスクのタイトル")
    scheduled_date: date | None = Field(default=None, description="日付 (YYYY-MM-DD)")
    start_time: str | None = Field(default=None, description="開始時刻 (HH:MM)。ユーザーが明示した場合のみ。推測禁止")
    end_time: str | None = Field(default=None, description="終了時刻 (HH:MM)。ユーザーが明示した場合のみ。推測禁止")
    follow_up_question: str | None = Field(default=None, description="不足情報を1つだけ聞く質問文")
    reply: str = Field(default="", description="ユーザーへの返答文（ユーザーと同じ言語で）")
    needs_web_search: bool = Field(default=False, description="最新情報の取得にウェブ検索が必要かどうか")
