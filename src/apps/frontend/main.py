import base64
import json
import os
import uuid

import requests
import streamlit as st

from packages.core.config import settings
from packages.core.infrastructure import socket
from packages.core.logging import logger

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")

st.set_page_config(page_title="AIly Chat", layout="centered")
st.title("AIly Chat")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


def render_image_thumbnail(data_url: str, key_prefix: str) -> None:
    thumb_id = f"thumb_{key_prefix}"
    overlay_id = f"overlay_{key_prefix}"
    st.html(
        f"""
        <img id="{thumb_id}" src="{data_url}"
             style="max-height:140px;max-width:200px;border-radius:8px;
                    cursor:zoom-in;display:block;margin:4px 0;object-fit:cover;">
        <div id="{overlay_id}"
             style="display:none;position:fixed;top:0;left:0;
                    width:100vw;height:100vh;background:rgba(0,0,0,0.88);
                    z-index:99999;justify-content:center;align-items:center;
                    cursor:zoom-out;">
          <img src="{data_url}"
               style="max-width:90vw;max-height:90vh;border-radius:8px;object-fit:contain;">
        </div>
        <script>
        (function() {{
          var thumb = document.getElementById('{thumb_id}');
          var overlay = document.getElementById('{overlay_id}');
          if (thumb && overlay && !thumb._bound) {{
            thumb._bound = true;
            thumb.addEventListener('click', function() {{
              overlay.style.display = 'flex';
            }});
            overlay.addEventListener('click', function() {{
              overlay.style.display = 'none';
            }});
          }}
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("image_base64"):
            data_url = f"data:{msg['image_mime_type']};base64,{msg['image_base64']}"
            render_image_thumbnail(data_url, key_prefix=f"log_{i}")


def stream_reply(
    message: str,
    session_id: str,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
):
    with requests.post(
        f"{API_BASE_URL}/chat",
        json={
            "message": message,
            "session_id": session_id,
            "image_base64": image_base64,
            "image_mime_type": image_mime_type,
        },
        stream=True,
        timeout=120,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if not decoded.startswith("data: "):
                continue
            data = decoded[6:]
            if data == "[DONE]":
                break
            yield json.loads(data)


prompt = st.chat_input("メッセージを入力", accept_file=True, file_type=["jpg", "jpeg", "png", "webp"])

if prompt and prompt.text:
    message = prompt.text
    uploaded_file = prompt.files[0] if prompt.files else None

    image_base64 = None
    image_mime_type = None
    if uploaded_file:
        image_base64 = base64.b64encode(uploaded_file.read()).decode()
        image_mime_type = uploaded_file.type

    st.session_state.messages.append(
        {
            "role": "user",
            "content": message,
            "image_base64": image_base64,
            "image_mime_type": image_mime_type,
        }
    )

    with st.chat_message("user"):
        st.write(message)
        if image_base64 and image_mime_type:
            data_url = f"data:{image_mime_type};base64,{image_base64}"
            render_image_thumbnail(data_url, key_prefix="new_input")

    with st.chat_message("assistant"):
        try:
            with st.spinner("考え中..."):
                reply = st.write_stream(stream_reply(message, st.session_state.session_id, image_base64, image_mime_type))
        except Exception:
            reply = "エラーが発生しました。しばらくしてから再試行してください。"
            st.error(reply)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": reply,
            "image_base64": None,
            "image_mime_type": None,
        }
    )

    st.rerun()


if settings.app_env == "local":
    is_debug = False
    try:
        import pydevd_pycharm

        try:
            if socket.is_debug_server_ready("host.docker.internal", 12346):
                pydevd_pycharm.settrace("host.docker.internal", port=12346, stdout_to_server=True, stderr_to_server=True, suspend=False)
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
