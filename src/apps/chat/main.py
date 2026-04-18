import json
import os
import uuid

import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")

st.set_page_config(page_title="AIly Chat", layout="centered")
st.title("AIly Chat")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])


def stream_reply(message: str, session_id: str):
    with requests.post(
        f"{API_BASE_URL}/chat",
        json={"message": message, "session_id": session_id},
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


if prompt := st.chat_input("メッセージを入力"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(stream_reply(prompt, st.session_state.session_id))
        except Exception as e:
            reply = "エラーが発生しました。しばらくしてから再試行してください。"
            st.error(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
