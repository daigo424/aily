import streamlit as st

from apps.admin.common import api_get, api_patch
from packages.core.constants import ReservationStatus

reservation_id = st.session_state.pop("reservation_id", None) or st.query_params.get("reservation_id")

if not reservation_id:
    st.warning("予約IDが指定されていません。予約一覧から遷移してください。")
    if st.button("← 予約一覧へ"):
        st.switch_page("pages/reservations.py")
    st.stop()

reservation_id = int(reservation_id)

try:
    row = api_get(f"/admin/reservations/{reservation_id}")
except Exception:
    row = None

if not row:
    st.error(f"予約 ID {reservation_id} が見つかりません。")
    if st.button("← 予約一覧へ"):
        st.session_state.pop("reservation_id", None)
        st.switch_page("pages/reservations.py")
    st.stop()

st.title(f"予約詳細 #{row['id']}")
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


def fmt_dt(val: str | None) -> str:
    if not val:
        return "―"
    return val[:16]


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

current = row["status"]
if current == ReservationStatus.CANCELLED:
    st.info("顧客によりキャンセルされた予約です。ステータスを変更できません。")
else:
    btn_col1, btn_col2 = st.columns(2)
    if current != ReservationStatus.COMPLETED:
        if btn_col1.button("✅ 完了にする"):
            api_patch(f"/admin/reservations/{reservation_id}/status", {"status": ReservationStatus.COMPLETED})
            st.success("完了に更新しました。")
            st.rerun()
    if current != ReservationStatus.VOIDED:
        if btn_col2.button("🚫 無効にする"):
            api_patch(f"/admin/reservations/{reservation_id}/status", {"status": ReservationStatus.VOIDED})
            st.success("無効に更新しました。")
            st.rerun()

st.divider()

st.subheader("顧客情報")
col1, col2 = st.columns(2)
col1.metric("氏名", row["customer_name"] or "―")
col2.metric("電話番号", row["phone"])

if st.button("💬 会話履歴を見る"):
    st.session_state.pop("reservation_id", None)
    st.session_state["customer_phone"] = row["phone"]
    st.switch_page("pages/customer_messages.py")

st.divider()

if row["booking_request_id"]:
    st.subheader("予約リクエスト")
    col1, col2 = st.columns(2)
    col1.metric("リクエストID", row["booking_request_id"])
    col2.metric("ステータス", row["booking_request_status"])

    entities = row["extracted_entities"]
    if entities:
        st.markdown("**抽出エンティティ**")
        st.json(entities)
