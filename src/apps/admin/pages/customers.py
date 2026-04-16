import streamlit as st

from apps.admin.common import fetch_df

st.title("顧客一覧")

PAGE_SIZE = 20

total_row = fetch_df("""
    select count(distinct c.id) as cnt
    from customers c
    join messages m on m.customer_id = c.id
""")
total = int(total_row["cnt"].iloc[0]) if not total_row.empty else 0
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

page = st.number_input("ページ", min_value=1, max_value=total_pages, value=1, step=1)
st.caption(f"{total} 件 / {total_pages} ページ")

offset = (page - 1) * PAGE_SIZE

customers = fetch_df(
    """
    select
      c.id,
      c.name,
      c.phone,
      max(m.created_at) as last_message_at,
      count(distinct conv.id) as conversation_count
    from customers c
    join messages m on m.customer_id = c.id
    join conversations conv on conv.customer_id = c.id
    group by c.id, c.name, c.phone
    order by last_message_at desc
    limit :limit offset :offset
    """,
    {"limit": PAGE_SIZE, "offset": offset},
)

if customers.empty:
    st.info("顧客が見つかりません。")
else:
    for _, row in customers.iterrows():
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        col1.write(row["name"] or "―")
        col2.write(row["phone"])
        col3.write(str(row["last_message_at"])[:19])
        if col4.button("💬 会話履歴", key=f"btn_{row['phone']}"):
            st.session_state["customer_phone"] = row["phone"]
            st.switch_page("pages/customer_messages.py")
