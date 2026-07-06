import streamlit as st

from apps.admin.common import api_delete, api_get, api_patch
from packages.core.constants import TaskStatus

st.title("タスク一覧")

data = api_get("/admin/tasks")
items = data["items"]

STATUS_LABEL = {
    TaskStatus.NOT_STARTED: "未着手",
    TaskStatus.DOING: "進行中",
    TaskStatus.DONE: "完了",
}

STATUS_OPTIONS = [TaskStatus.NOT_STARTED, TaskStatus.DOING, TaskStatus.DONE]


def fmt_dt(val: str | None) -> str:
    if not val:
        return "―"
    return val[:16]


if not items:
    st.info("タスクデータがありません。")
else:
    col_widths = [0.5, 3, 2, 2, 1.5, 3, 1, 1]
    headers = ["ID", "タイトル", "開始", "終了", "ステータス", "メモ", "", ""]
    header_cols = st.columns(col_widths)
    for col, label in zip(header_cols, headers):
        col.markdown(f"**{label}**")
    st.divider()

    for row in items:
        tid = row["id"]
        status = row["status"]
        cols = st.columns(col_widths)
        cols[0].write(tid)
        cols[1].write(row["title"])
        cols[2].write(fmt_dt(row["starts_at"]))
        cols[3].write(fmt_dt(row["ends_at"]))
        cols[4].write(STATUS_LABEL.get(status, status))
        cols[5].write(row["notes"] or "―")

        if cols[6].button("編集", key=f"edit_t_{tid}"):
            st.session_state["edit_task_id"] = tid
            st.rerun()

        if cols[7].button("🗑", key=f"del_t_{tid}", help="削除"):
            api_delete(f"/admin/tasks/{tid}")
            st.rerun()

# --- Edit form ---
if "edit_task_id" in st.session_state:
    tid = st.session_state["edit_task_id"]
    task = api_get(f"/admin/tasks/{tid}")
    st.divider()
    st.subheader(f"タスク編集 (ID: {tid})")
    with st.form(f"form_task_{tid}"):
        new_title = st.text_input("タイトル", value=task["title"])
        new_starts = st.text_input("開始日時 (ISO形式)", value=(task["starts_at"] or "")[:16])
        new_ends = st.text_input("終了日時 (ISO形式)", value=(task["ends_at"] or "")[:16])
        current_idx = STATUS_OPTIONS.index(task["status"]) if task["status"] in STATUS_OPTIONS else 0
        new_status = st.selectbox(
            "ステータス",
            options=STATUS_OPTIONS,
            index=current_idx,
            format_func=lambda s: STATUS_LABEL.get(s, s),
        )
        new_notes = st.text_area("メモ", value=task["notes"] or "")
        submitted = st.form_submit_button("保存")
        if submitted:
            api_patch(
                f"/admin/tasks/{tid}",
                {"title": new_title, "starts_at": new_starts, "ends_at": new_ends, "status": new_status, "notes": new_notes or None},
            )
            del st.session_state["edit_task_id"]
            st.rerun()
