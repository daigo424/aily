import asyncio
import base64
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from packages.core.db.repositories import Repository
from packages.core.db.session import SessionLocal
from packages.core.graph.state import ScheduleState
from packages.core.infrastructure.storage import backend as storage
from packages.core.logging import logger
from packages.core.usecases import generate_title

router = APIRouter()

_TITLE_INTERVAL = 10  # every 5 exchanges (10 messages)


def _should_generate_title(msg_count: int) -> bool:
    return msg_count >= 2 and (msg_count - 2) % _TITLE_INTERVAL == 0


class ChatRequest(BaseModel):
    message: str
    chat_id: int
    image_base64: str | None = None
    image_mime_type: str | None = None


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    async def generate() -> AsyncGenerator[str, None]:
        db: Session = SessionLocal()
        repo = Repository(db)
        try:
            current_chat = repo.get_chat(body.chat_id)
            if not current_chat:
                yield f"data: {json.dumps('チャットが見つかりません。')}\n\n"
                yield "data: [DONE]\n\n"
                return

            msg_type = "image" if body.image_base64 else "text"
            saved_message = repo.save_message(
                chat=current_chat,
                direction="inbound",
                message_type=msg_type,
                text_content=body.message,
                raw_llm_result={},
            )
            db.flush()

            if body.image_base64:
                image_bytes = base64.b64decode(body.image_base64)
                mime = body.image_mime_type or "image/jpeg"
                ext = mime.split("/")[-1].replace("jpeg", "jpg")
                key = f"{uuid.uuid4()}.{ext}"
                storage.save(key, image_bytes, mime)
                repo.save_attachment(
                    message_id=saved_message.id,
                    file_name=key,
                    storage_key=key,
                    mime_type=mime,
                    file_size=len(image_bytes),
                )

            initial_state = ScheduleState(
                messages=[HumanMessage(content=body.message, additional_kwargs={"created_at": datetime.now(timezone.utc).isoformat()})],
                text_body=body.message,
                sender=f"web_{body.chat_id}",
                chat_id=body.chat_id,
                raw_llm_result={},
                intent="",
                reply="...",
                image_base64=body.image_base64,
                image_mime_type=body.image_mime_type,
            )

            loop = asyncio.get_running_loop()
            schedule_graph = request.app.state.schedule_graph
            graph_config = {
                "configurable": {
                    "thread_id": str(body.chat_id),
                    "repo": repo,
                    "chat": current_chat,
                    "source_message": saved_message,
                    "image_base64": body.image_base64,
                    "image_mime_type": body.image_mime_type,
                }
            }
            # PostgresSaver は同期のみ対応のため stream() を run_in_executor で動かし、
            # Queue 経由でノードイベントを非同期コンテキストに渡す。
            queue: asyncio.Queue = asyncio.Queue()

            def _run_graph() -> None:
                try:
                    for event in schedule_graph.stream(initial_state, config=graph_config):
                        loop.call_soon_threadsafe(queue.put_nowait, event)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            executor_future = loop.run_in_executor(None, _run_graph)
            result: dict = {}
            while True:
                event = await queue.get()
                if event is None:
                    break
                node_name = next(iter(event))
                result.update(event[node_name])
                if node_name == "llm_extraction" and result.get("raw_llm_result", {}).get("needs_web_search"):
                    yield f"data: {json.dumps({'type': 'web_searching'})}\n\n"
            await executor_future

            saved_message.raw_llm_result = result["raw_llm_result"]
            reply: str = result["reply"]

            repo.save_message(
                chat=current_chat,
                direction="outbound",
                message_type="text",
                text_content=reply,
                raw_llm_result={},
            )

            # タイトル生成（1回目 or 5往復ごと）
            msg_count = repo.count_messages(body.chat_id)
            new_title: str | None = None
            if _should_generate_title(msg_count):
                recent_msgs = result.get("messages", [])[-8:]
                new_title = await loop.run_in_executor(None, lambda: generate_title.execute(recent_msgs))
                if new_title:
                    repo.update_chat_title(body.chat_id, new_title)

            db.commit()

            for word in reply.split(" "):
                yield f"data: {json.dumps(word + ' ')}\n\n"
                await asyncio.sleep(0.04)

            if new_title:
                yield f"data: {json.dumps({'type': 'title_update', 'title': new_title, 'chat_id': body.chat_id})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            db.rollback()
            logger.exception(f"Chat failed: {e}")
            yield f"data: {json.dumps('エラーが発生しました。')}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
