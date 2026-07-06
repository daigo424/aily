import streamlit as st

from apps.admin.common import api_delete, api_get, api_patch

st.title("予定一覧")

data = api_get("/admin/events")
items = data["items"]


def fmt_dt(val: str | None) -> str:
    if not val:
        return "―"
    return val[:16]


if not items:
    st.info("予定データがありません。")
else:
    col_widths = [0.5, 3, 2, 2, 3, 1, 1]
    headers = ["ID", "タイトル", "開始", "終了", "メモ", "", ""]
    header_cols = st.columns(col_widths)
    for col, label in zip(header_cols, headers):
        col.markdown(f"**{label}**")
    st.divider()

    for row in items:
        eid = row["id"]
        cols = st.columns(col_widths)
        cols[0].write(eid)
        cols[1].write(row["title"])
        cols[2].write(fmt_dt(row["starts_at"]))
        cols[3].write(fmt_dt(row["ends_at"]))
        cols[4].write(row["notes"] or "―")

        if cols[5].button("編集", key=f"edit_e_{eid}"):
            st.session_state["edit_event_id"] = eid
            st.rerun()

        if cols[6].button("🗑", key=f"del_e_{eid}", help="削除"):
            api_delete(f"/admin/events/{eid}")
            st.rerun()

# --- Edit form ---
if "edit_event_id" in st.session_state:
    eid = st.session_state["edit_event_id"]
    ev = api_get(f"/admin/events/{eid}")
    st.divider()
    st.subheader(f"予定編集 (ID: {eid})")
    with st.form(f"form_event_{eid}"):
        new_title = st.text_input("タイトル", value=ev["title"])
        new_starts = st.text_input("開始日時 (ISO形式)", value=(ev["starts_at"] or "")[:16])
        new_ends = st.text_input("終了日時 (ISO形式)", value=(ev["ends_at"] or "")[:16])
        new_notes = st.text_area("メモ", value=ev["notes"] or "")
        submitted = st.form_submit_button("保存")
        if submitted:
            api_patch(
                f"/admin/events/{eid}",
                {"title": new_title, "starts_at": new_starts, "ends_at": new_ends, "notes": new_notes or None},
            )
            del st.session_state["edit_event_id"]
            st.rerun()
