from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.types import RunnableConfig

from packages.core.config import settings
from packages.core.constants import ConversationIntent, ScheduleDraftStatus
from packages.core.db.models import Chat, Message
from packages.core.db.repositories import Repository
from packages.core.usecases import extract_schedule

from .state import ScheduleState

_HISTORY_WINDOW = timedelta(days=1)


def _repo(config: RunnableConfig) -> Repository:
    return cast(Repository, config["configurable"]["repo"])


def _chat(config: RunnableConfig) -> Chat:
    return cast(Chat, config["configurable"]["chat"])


def _source_message(config: RunnableConfig) -> Message:
    return cast(Message, config["configurable"]["source_message"])


def _ai_message(reply: str) -> AIMessage:
    return AIMessage(content=reply, additional_kwargs={"created_at": datetime.now(timezone.utc).isoformat()})


def _is_recent(msg: BaseMessage) -> bool:
    ts_str = msg.additional_kwargs.get("created_at")
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts >= datetime.now(timezone.utc) - _HISTORY_WINDOW
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Node: LLM extraction
# ---------------------------------------------------------------------------


def llm_extraction_node(state: ScheduleState, config: RunnableConfig) -> dict:
    text_body = state["text_body"]
    if not text_body:
        return {"raw_llm_result": {}, "intent": ConversationIntent.UNKNOWN}

    all_prior = state.get("messages", [])[:-1]
    prior_messages = [m for m in all_prior if _is_recent(m)][-20:]

    raw_llm_result = extract_schedule.execute(
        text_body,
        history=prior_messages,
        image_base64=state.get("image_base64"),
        image_mime_type=state.get("image_mime_type"),
    )
    intent = raw_llm_result.get("intent", ConversationIntent.UNKNOWN)

    current_chat = _chat(config)
    current_chat.current_intent = intent

    return {"raw_llm_result": raw_llm_result, "intent": intent}


# ---------------------------------------------------------------------------
# Node: add schedule intent — collect info and confirm when ready
# ---------------------------------------------------------------------------


def handle_add_schedule_node(state: ScheduleState, config: RunnableConfig) -> dict:
    repo = _repo(config)
    current_chat = _chat(config)
    source_message = _source_message(config)

    draft = repo.create_or_update_schedule_draft(
        chat=current_chat,
        source_message=source_message,
        parsed=state["raw_llm_result"],
    )

    if draft.status != ScheduleDraftStatus.READY:
        reply = state["raw_llm_result"].get("follow_up_question") or state["raw_llm_result"].get("reply") or "詳細を教えてください。"
        return {"reply": reply, "messages": [_ai_message(reply)]}

    item = repo.confirm_schedule_from_draft(draft)
    tz = ZoneInfo(settings.timezone)
    starts_local = item.starts_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    ends_local = item.ends_at.astimezone(tz).strftime("%H:%M")
    item_label = "タスク" if draft.item_type == "task" else "予定"
    reply = f"「{item.title}」を{item_label}として記録しました。\n日時: {starts_local}〜{ends_local}（{settings.timezone}）"
    return {"reply": reply, "messages": [_ai_message(reply)]}


# ---------------------------------------------------------------------------
# Node: list schedule intent — show upcoming events and tasks
# ---------------------------------------------------------------------------


def handle_list_schedule_node(state: ScheduleState, config: RunnableConfig) -> dict:
    repo = _repo(config)
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(timezone.utc)

    events = [e for e in repo.list_events() if e.starts_at >= now][:10]
    tasks = [t for t in repo.list_tasks() if t.starts_at >= now][:10]

    if not events and not tasks:
        reply = "今後の予定・タスクはまだ登録されていません。"
        return {"reply": reply, "messages": [_ai_message(reply)]}

    lines: list[str] = []
    if events:
        lines.append("【予定】")
        for e in sorted(events, key=lambda x: x.starts_at):
            s = e.starts_at.astimezone(tz).strftime("%m/%d %H:%M")
            en = e.ends_at.astimezone(tz).strftime("%H:%M")
            lines.append(f"・{e.title}  {s}〜{en}")
    if tasks:
        lines.append("【タスク】")
        status_label = {"not_started": "未着手", "doing": "進行中", "done": "完了"}
        for t in sorted(tasks, key=lambda x: x.starts_at):
            s = t.starts_at.astimezone(tz).strftime("%m/%d %H:%M")
            en = t.ends_at.astimezone(tz).strftime("%H:%M")
            sl = status_label.get(t.status, t.status)
            lines.append(f"・{t.title}  {s}〜{en}  [{sl}]")

    reply = "\n".join(lines)
    return {"reply": reply, "messages": [_ai_message(reply)]}


# ---------------------------------------------------------------------------
# Node: other intents (smalltalk, unknown)
# ---------------------------------------------------------------------------


def handle_other_intent_node(state: ScheduleState, config: RunnableConfig) -> dict:
    reply = state["raw_llm_result"].get("reply") or "..."
    return {"reply": reply, "messages": [_ai_message(reply)]}
