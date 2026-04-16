import streamlit as st
from sqlalchemy.orm import Session

from apps.admin.common import engine, fetch_df
from packages.core.constants import ReservationStatus
from packages.core.db.repositories import Repository

st.title("予約一覧")

col1, col2, col3 = st.columns(3)
show_completed = col1.checkbox("完了済みを含む", value=False)
show_voided = col2.checkbox("無効を含む", value=False)
show_cancelled = col3.checkbox("キャンセル済みを含む", value=False)

excluded = []
if not show_completed:
    excluded.append(f"'{ReservationStatus.COMPLETED}'")
if not show_voided:
    excluded.append(f"'{ReservationStatus.VOIDED}'")
if not show_cancelled:
    excluded.append(f"'{ReservationStatus.CANCELLED}'")

where_clause = f"where r.status not in ({', '.join(excluded)})" if excluded else ""

df = fetch_df(
    f"""
    select
      r.id,
      r.reservation_code,
      r.status,
      r.reserved_for,
      r.completed_at,
      r.voided_at,
      r.cancelled_at,
      c.name as customer_name,
      c.phone
    from reservations r
    join customers c on c.id = r.customer_id
    {where_clause}
    order by r.reserved_for desc
    """
)

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


def update_status(reservation_id: int, status: ReservationStatus) -> None:
    with Session(engine) as db:
        Repository(db).update_reservation_status(reservation_id, status)
        db.commit()


if df.empty:
    st.info("予約データがありません。")
else:
    col_widths = [1, 2, 1.5, 2, 2, 2, 2, 2, 2, 1, 1, 1]
    headers = ["ID", "予約コード", "ステータス", "予約日時", "完了日時", "無効日時", "キャンセル日時", "顧客名", "電話番号", "", "", ""]
    header_cols = st.columns(col_widths)
    for col, label in zip(header_cols, headers):
        col.markdown(f"**{label}**")
    st.divider()

    for _, row in df.iterrows():
        rid = int(row["id"])
        status = row["status"]
        cols = st.columns(col_widths)
        cols[0].write(rid)
        cols[1].write(row["reservation_code"])
        cols[2].write(STATUS_LABEL.get(status, status))
        cols[3].write(fmt_dt(row["reserved_for"]))
        cols[4].write(fmt_dt(row.get("completed_at")))
        cols[5].write(fmt_dt(row.get("voided_at")))
        cols[6].write(fmt_dt(row.get("cancelled_at")))
        cols[7].write(row["customer_name"] or "―")
        cols[8].write(row["phone"])
        if status != ReservationStatus.CANCELLED:
            if status != ReservationStatus.COMPLETED:
                if cols[9].button("✅", key=f"done_{rid}", help="完了にする"):
                    update_status(rid, ReservationStatus.COMPLETED)
                    st.rerun()
            if status != ReservationStatus.VOIDED:
                if cols[10].button("🚫", key=f"cancel_{rid}", help="無効にする"):
                    update_status(rid, ReservationStatus.VOIDED)
                    st.rerun()
        if cols[11].button("詳細", key=f"res_{rid}"):
            st.session_state["reservation_id"] = rid
            st.switch_page("pages/reservation_detail.py")
