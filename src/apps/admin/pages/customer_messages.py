import streamlit as st
import streamlit.components.v1 as components

from apps.admin.common import api_get, api_post

PAGE_SIZE = 50
PREFETCH_AT = 40

st.title("顧客メッセージ")

default_phone = st.session_state.pop("customer_phone", "") or st.query_params.get("phone", "")
phone = st.text_input("電話番号", value=default_phone)

if phone and phone != st.query_params.get("phone", ""):
    st.query_params["phone"] = phone
    st.query_params.pop("page", None)
    st.rerun()

page = int(st.query_params.get("page", "0"))

if phone:
    customer: dict | None
    try:
        customer = api_get(f"/admin/customers/{phone}")
    except Exception:
        customer = None

    if not customer:
        st.warning("該当する顧客が見つかりません。")
    else:
        st.markdown(f"**{customer['name'] or '名前未登録'}** / {customer['phone']}")

        data = api_get(f"/admin/customers/{phone}/messages", {"page": page, "per_page": PAGE_SIZE})
        messages = data["items"]
        has_more = data["has_more"]

        st.subheader("会話履歴")
        if not messages:
            st.info("メッセージがありません。")
        else:
            total = len(messages)
            sentinel_index = page * PAGE_SIZE + PREFETCH_AT - 1

            for i, msg in enumerate(messages):
                is_outbound = msg["direction"] == "outbound"
                col_spacer, col_bubble = st.columns([1, 3]) if is_outbound else st.columns([3, 1])
                target_col = col_bubble if is_outbound else col_spacer
                label = "送信" if is_outbound else "受信"
                target_col.markdown(
                    f"<div style='background:{'#DCF8C6' if is_outbound else '#F0F0F0'};color:#666;"
                    f"padding:8px 12px;border-radius:8px;margin:4px 0;font-size:0.9em'>"
                    f"<small style='color:#888'>{label} · {(msg['created_at'] or '')[:16]}</small><br>"
                    f"{msg['text_content'] or '[' + msg['message_type'] + ']'}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if i == sentinel_index and has_more:
                    next_page = page + 1
                    components.html(
                        f"""
                        <div id="load-sentinel" style="height:1px;width:100%"></div>
                        <script>
                        (function() {{
                            var triggered = false;
                            var sentinel = document.getElementById('load-sentinel');
                            if (!sentinel) return;
                            var observer = new IntersectionObserver(function(entries) {{
                                if (entries[0].isIntersecting && !triggered) {{
                                    triggered = true;
                                    observer.disconnect();
                                    var url = new URL(window.parent.location.href);
                                    url.searchParams.set('page', '{next_page}');
                                    window.parent.location.href = url.toString();
                                }}
                            }}, {{threshold: 0.1}});
                            observer.observe(sentinel);
                        }})();
                        </script>
                        """,
                        height=1,
                    )

            if not has_more:
                st.caption(f"全 {total} 件を表示しています。")

        st.divider()
        st.subheader("メッセージを送信")
        with st.form("send_form", clear_on_submit=True):
            body = st.text_area("メッセージ本文", height=100)
            submitted = st.form_submit_button("送信")
        if submitted:
            if not body.strip():
                st.warning("本文を入力してください。")
            else:
                try:
                    api_post(f"/admin/customers/{phone}/messages", {"text": body.strip()})
                    st.success("送信しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"送信に失敗しました: {e}")
else:
    st.info("電話番号を入力すると、その顧客のメッセージ履歴を表示します。")
