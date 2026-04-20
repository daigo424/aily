import os
import sys

import streamlit as st

root_path = os.environ.get("APP_ROOT")
if root_path not in sys.path:
    sys.path.insert(0, root_path)

st.set_page_config(page_title="WhatsApp Booking Admin", layout="wide")

customers_page = st.Page("pages/customers.py", title="顧客一覧")
reservations_page = st.Page("pages/reservations.py", title="予約一覧")
messages_page = st.Page("pages/customer_messages.py", title="顧客メッセージ")
detail_page = st.Page("pages/reservation_detail.py", title="予約詳細", url_path="reservation_detail")

pg = st.navigation(
    [customers_page, reservations_page, messages_page, detail_page],
    position="hidden",
)

with st.sidebar:
    st.title("Admin")
    st.page_link(customers_page, label="顧客一覧")
    st.page_link(reservations_page, label="予約一覧")
    st.page_link(messages_page, label="顧客メッセージ")

pg.run()
