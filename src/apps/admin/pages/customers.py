import streamlit as st

from apps.admin.common import api_get

st.title("顧客一覧")

PAGE_SIZE = 20

page = st.number_input("ページ", min_value=1, value=1, step=1)

data = api_get("/admin/customers", {"page": page, "per_page": PAGE_SIZE})
total = data["total"]
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
st.caption(f"{total} 件 / {total_pages} ページ")

customers = data["items"]

if not customers:
    st.info("顧客が見つかりません。")
else:
    for row in customers:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        col1.write(row["name"] or "―")
        col2.write(row["phone"])
        col3.write((row["last_message_at"] or "")[:19])
        if col4.button("💬 会話履歴", key=f"btn_{row['phone']}"):
            st.session_state["customer_phone"] = row["phone"]
            st.switch_page("pages/customer_messages.py")
