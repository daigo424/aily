import os
import sys

import streamlit as st

root_path = os.environ.get("APP_ROOT")
if root_path is not None and root_path not in sys.path:
    sys.path.insert(0, root_path)

st.set_page_config(page_title="Aily Admin", layout="wide")

events_page = st.Page("pages/events.py", title="予定一覧")
tasks_page = st.Page("pages/tasks.py", title="タスク一覧")

pg = st.navigation(
    [events_page, tasks_page],
    position="hidden",
)

with st.sidebar:
    st.title("Admin")
    st.page_link(events_page, label="予定一覧")
    st.page_link(tasks_page, label="タスク一覧")

pg.run()
