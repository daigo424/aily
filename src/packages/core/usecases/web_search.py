from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from packages.core.config import settings
from packages.core.infrastructure import llm

_MAX_RESULTS = 5


def _to_api_messages(messages: list[BaseMessage]) -> list[dict]:
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
    return result


def _make_search_query(
    text: str,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
) -> str:
    today = datetime.now(tz=ZoneInfo(settings.timezone)).strftime("%Y-%m-%d")
    prompt = f"今日: {today}\n次のメッセージを検索エンジン向けの短いクエリ（キーワード数個）に変換してください。クエリのみを返し、説明は不要です。\nメッセージ: {text}"
    query = llm.client.gen_text(
        prompt=prompt,
        temperature=0.0,
        image_base64=image_base64,
        image_mime_type=image_mime_type,
    ).strip()
    if not query or len(query) > 120:
        return text
    return query


def _build_context(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        snippet = r.get("content", "")
        url = r.get("url", "")
        lines.append(f"{i}. {title}\n   {snippet}\n   URL: {url}")
    return "\n\n".join(lines)


def execute(
    text: str,
    history: list[BaseMessage] | None = None,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
) -> dict:
    results: list[dict] = []

    if settings.searxng_url:
        search_query = _make_search_query(text, image_base64=image_base64, image_mime_type=image_mime_type)
        try:
            resp = httpx.get(
                f"{settings.searxng_url.rstrip('/')}/search",
                params={"q": search_query, "format": "json", "language": "ja-JP"},
                headers={"X-Forwarded-For": "127.0.0.1"},
                timeout=10.0,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])[:_MAX_RESULTS]
        except Exception:
            pass

    has_image = bool(image_base64)
    if results:
        context = _build_context(results)
        image_note = "\n- 画像が添付されている場合は、画像の内容も確認して回答に活かすこと" if has_image else ""
        system_prompt = f"""ウェブ検索で得た最新情報をもとに、ユーザーの質問に答えてください。

- ユーザーのメッセージと同じ言語で答えること
- 「調べたところ〜」「最新情報によると〜」のように検索で得た情報であることが伝わるように答えること
- 情報の出典URLを自然な形で含めること
- 検索結果に答えがない場合はその旨を伝えること{image_note}

【検索結果】
{context}"""
    else:
        image_note = "画像が添付されている場合はその内容も確認し、" if has_image else ""
        system_prompt = f"""ウェブ検索を試みましたが結果が得られませんでした。
{image_note}知っている範囲で答えてください。ユーザーのメッセージと同じ言語で答えること。"""

    api_history = _to_api_messages(history) if history else None
    reply = llm.client.gen_text(
        prompt=text,
        system_prompt=system_prompt,
        history=api_history,
        image_base64=image_base64,
        image_mime_type=image_mime_type,
    )
    return {"reply": reply}
