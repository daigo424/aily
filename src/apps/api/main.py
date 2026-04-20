from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from apps.api.routers import admin, chat, webhook
from packages.core.config import settings
from packages.core.graph import build_graph
from packages.core.infrastructure import socket
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

app.include_router(webhook.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> dict:
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
