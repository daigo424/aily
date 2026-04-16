import json

import streamlit as st
from sqlalchemy.orm import Session

from apps.admin.common import engine, fetch_df
from packages.core.constants import ReservationStatus
from packages.core.db.repositories import Repository

reservation_id = st.session_state.pop("reservation_id", None) or st.query_params.get("reservation_id")

if not reservation_id:
    st.warning("予約IDが指定されていません。予約一覧から遷移してください。")
    if st.button("← 予約一覧へ"):
        st.switch_page("pages/reservations.py")
    st.stop()

reservation_id = int(reservation_id)

detail = fetch_df(
    """
    select
      r.id,
      r.reservation_code,
      r.status,
      r.reserved_for,
      r.completed_at,
      r.voided_at,
      r.cancelled_at,
      r.notes,
      c.id as customer_id,
      c.name as customer_name,
      c.phone,
      br.id as booking_request_id,
      br.status as booking_request_status,
      br.extracted_entities,
      r.created_at,
      r.updated_at
    from reservations r
    join customers c on c.id = r.customer_id
    left join booking_requests br on br.id = r.booking_request_id
    where r.id = :reservation_id
    """,
    {"reservation_id": reservation_id},
)

if detail.empty:
    st.error(f"予約 ID {reservation_id} が見つかりません。")
    if st.button("← 予約一覧へ"):
        st.session_state.pop("reservation_id", None)
        st.switch_page("pages/reservations.py")
    st.stop()

row = detail.iloc[0]

st.title(f"予約詳細 #{int(row['id'])}")
if st.button("← 予約一覧へ"):
    st.session_state.pop("reservation_id", None)
    st.switch_page("pages/reservations.py")

st.divider()

STATUS_LABEL = {
    ReservationStatus.PENDING: "確認中",
    ReservationStatus.COMPLETED: "完了",
    ReservationStatus.VOIDED: "無効",
    ReservationStatus.CANCELLED: "キャンセル",
}


def fmt_dt(val) -> str:
    if val is None or str(val) in ("None", "NaT", ""):
        return "―"
    return str(val)[:16]


# 予約情報
st.subheader("予約情報")
col1, col2 = st.columns(2)
col1.metric("予約コード", row["reservation_code"])
col2.metric("ステータス", STATUS_LABEL.get(row["status"], row["status"]))

col3, col4 = st.columns(2)
col3.metric("予約日時", fmt_dt(row["reserved_for"]))
col4.metric("登録日時", fmt_dt(row["created_at"]))

col5, col6, col7 = st.columns(3)
col5.metric("完了日時", fmt_dt(row.get("completed_at")))
col6.metric("無効日時", fmt_dt(row.get("voided_at")))
col7.metric("キャンセル日時", fmt_dt(row.get("cancelled_at")))

if row["notes"]:
    st.markdown(f"**メモ:** {row['notes']}")

# ステータス変更
current = row["status"]
if current == ReservationStatus.CANCELLED:
    st.info("顧客によりキャンセルされた予約です。ステータスを変更できません。")
else:
    btn_col1, btn_col2 = st.columns(2)
    if current != ReservationStatus.COMPLETED:
        if btn_col1.button("✅ 完了にする"):
            with Session(engine) as db:
                Repository(db).update_reservation_status(reservation_id, ReservationStatus.COMPLETED)
                db.commit()
            st.success("完了に更新しました。")
            st.rerun()
    if current != ReservationStatus.VOIDED:
        if btn_col2.button("🚫 無効にする"):
            with Session(engine) as db:
                Repository(db).update_reservation_status(reservation_id, ReservationStatus.VOIDED)
                db.commit()
            st.success("無効に更新しました。")
            st.rerun()

st.divider()

# 顧客情報
st.subheader("顧客情報")
col1, col2 = st.columns(2)
col1.metric("氏名", row["customer_name"] or "―")
col2.metric("電話番号", row["phone"])

if st.button("💬 会話履歴を見る"):
    st.session_state.pop("reservation_id", None)
    st.session_state["customer_phone"] = row["phone"]
    st.switch_page("pages/customer_messages.py")

st.divider()

# 予約リクエスト情報
if row["booking_request_id"]:
    st.subheader("予約リクエスト")
    col1, col2 = st.columns(2)
    col1.metric("リクエストID", int(row["booking_request_id"]))
    col2.metric("ステータス", row["booking_request_status"])

    entities = row["extracted_entities"]
    if entities:
        if isinstance(entities, str):
            entities = json.loads(entities)
        if entities:
            st.markdown("**抽出エンティティ**")
            st.json(entities)
