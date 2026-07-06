import asyncio
import base64
import json
import os
from urllib.parse import quote

import flet as ft
import httpx

# Flet forwards ws_max_size to websockets-sansio; patch the default before Flet starts
# so images up to 100 MB can be received without WebSocket disconnect / page reload.
# The 10 MB application limit below still applies — only the transport cap is raised here.
import uvicorn as _uvicorn

_orig_uvicorn_config_init = _uvicorn.Config.__init__


def _patched_uvicorn_config_init(self, *args, **kwargs):
    kwargs.setdefault("ws_max_size", 100 * 1024 * 1024)  # 100 MB transport limit
    _orig_uvicorn_config_init(self, *args, **kwargs)


_uvicorn.Config.__init__ = _patched_uvicorn_config_init

# FletStaticFiles receives WebSocket connections for unknown paths (e.g. stale Streamlit tabs
# trying /_stcore/stream). Patch it to close those gracefully instead of crashing.
import starlette.staticfiles as _sf  # noqa: E402

_orig_sf_call = _sf.StaticFiles.__call__


async def _sf_call_safe(self, scope, receive, send):
    if scope.get("type") == "websocket":
        await send({"type": "websocket.close", "code": 1008, "reason": "not found"})
        return
    await _orig_sf_call(self, scope, receive, send)


_sf.StaticFiles.__call__ = _sf_call_safe

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")
SIDEBAR_W = 260

# ── Color tokens ────────────────────────────────────────────────────────────
C_SIDEBAR = "#0c0c14"  # near-black, violet cast — sidebar ground
C_MAIN = "#111119"  # main content ground
C_SURFACE = "#1e1e2c"  # elevated card / input background
C_ACCENT = "#6d28d9"  # violet — primary action
C_USER_BG = "#2d1b69"  # deep indigo — user bubble
C_ASST_BG = "#1e1e2e"  # elevated dark surface — assistant bubble
C_USER_AVT = "#0e7490"  # teal — user avatar
C_BORDER = "#26263a"  # subtle border
C_TEXT = "#ddddf0"  # near-white with violet tint
C_TEXT_DIM = "#6868a0"  # muted text
C_TEXT_HNT = "#40405c"  # placeholder / hint


async def main(page: ft.Page) -> None:
    page.title = "AIly"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = C_MAIN
    page.padding = 0
    page.spacing = 0

    # ── State ────────────────────────────────────────────────────────────────
    current_chat_id: list[int | None] = [None]
    chats: list[dict] = []
    active_title_ctrl: list[ft.Text] = []
    pending_image: list[dict | None] = [None]  # {"base64": str, "mime_type": str}

    # ── API helpers ──────────────────────────────────────────────────────────
    async def api_get(path: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{API_BASE_URL}{path}", timeout=10)
            r.raise_for_status()
            return r.json()

    async def api_post(path: str, data: dict | None = None) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{API_BASE_URL}{path}", json=data or {}, timeout=10)
            r.raise_for_status()
            return r.json()

    # ── Sidebar ──────────────────────────────────────────────────────────────
    chat_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=2, expand=True)

    def rebuild_chat_list() -> None:
        chat_list_col.controls.clear()
        for ch in chats[:30]:
            cid = ch["id"]
            title = ch.get("title") or "新しいチャット"
            active = cid == current_chat_id[0]

            async def on_click(e, _id: int = cid) -> None:
                current_chat_id[0] = _id
                rebuild_chat_list()
                await show_chat()
                page.update()

            if active:
                item = ft.Container(
                    content=ft.Text(
                        title,
                        size=13,
                        color=C_TEXT,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=1,
                        weight=ft.FontWeight.W_500,
                    ),
                    padding=ft.Padding(left=12, right=12, top=9, bottom=9),
                    border_radius=8,
                    bgcolor="#1c1c2e",
                    border=ft.Border(left=ft.BorderSide(3, C_ACCENT)),
                    ink=True,
                    on_click=on_click,
                )
            else:
                item = ft.Container(
                    content=ft.Text(
                        title,
                        size=13,
                        color=C_TEXT_DIM,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=1,
                    ),
                    padding=ft.Padding(left=14, right=12, top=9, bottom=9),
                    border_radius=8,
                    ink=True,
                    on_click=on_click,
                )
            chat_list_col.controls.append(item)

    async def refresh_chats() -> None:
        nonlocal chats
        try:
            data = await api_get("/chats")
            chats = data["items"]
        except Exception:
            pass
        rebuild_chat_list()

    async def on_new_chat(e) -> None:
        current_chat_id[0] = None
        messages_lv.controls.clear()
        rebuild_chat_list()
        await show_top()
        page.update()

    async def on_go_search(e) -> None:
        await show_search()
        page.update()

    sidebar = ft.Container(
        width=SIDEBAR_W,
        bgcolor=C_SIDEBAR,
        content=ft.Column(
            controls=[
                # Brand
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text("A", size=14, color="white", weight=ft.FontWeight.BOLD),
                                width=30,
                                height=30,
                                border_radius=9,
                                bgcolor=C_ACCENT,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Text("AIly", size=17, weight=ft.FontWeight.BOLD, color=C_TEXT),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(left=16, right=16, top=20, bottom=16),
                ),
                # New chat
                ft.Container(
                    content=ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.ADD, size=16, color="white"),
                                ft.Text("新しいチャット", size=13, color="white", weight=ft.FontWeight.W_500),
                            ],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor=C_ACCENT,
                        border_radius=8,
                        padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                        ink=True,
                        on_click=on_new_chat,
                    ),
                    padding=ft.Padding(left=12, right=12, top=0, bottom=6),
                ),
                # Search
                ft.Container(
                    content=ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.SEARCH, size=15, color=C_TEXT_DIM),
                                ft.Text("チャットを検索", size=13, color=C_TEXT_DIM),
                            ],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        border_radius=8,
                        border=ft.Border(
                            top=ft.BorderSide(1, C_BORDER),
                            bottom=ft.BorderSide(1, C_BORDER),
                            left=ft.BorderSide(1, C_BORDER),
                            right=ft.BorderSide(1, C_BORDER),
                        ),
                        padding=ft.Padding(left=16, right=16, top=9, bottom=9),
                        ink=True,
                        on_click=on_go_search,
                    ),
                    padding=ft.Padding(left=12, right=12, top=0, bottom=12),
                ),
                # Divider + section label
                ft.Container(height=1, bgcolor=C_BORDER),
                ft.Container(
                    content=ft.Text("最近の会話", size=10, color=C_TEXT_DIM, weight=ft.FontWeight.W_600),
                    padding=ft.Padding(left=16, right=16, top=12, bottom=6),
                ),
                # Chat list
                ft.Container(
                    content=chat_list_col,
                    expand=True,
                    padding=ft.Padding(left=8, right=8, top=0, bottom=8),
                ),
            ],
            spacing=0,
            expand=True,
        ),
    )

    # ── Messages ─────────────────────────────────────────────────────────────
    messages_lv = ft.ListView(
        expand=True,
        spacing=12,
        auto_scroll=False,  # must be False for scroll_to() to work
        padding=ft.Padding(left=300, right=300, top=16, bottom=16),
    )

    async def _scroll_bottom(has_image: bool = False) -> None:
        try:
            await messages_lv.scroll_to(offset=-1, duration=150)
            if has_image:
                # Images are laid out asynchronously in Flutter; the first scroll_to
                # fires before the image height is known, leaving it partially off-screen.
                # Wait one render cycle then scroll again once the height is resolved.
                await asyncio.sleep(0.35)
                await messages_lv.scroll_to(offset=-1, duration=100)
        except Exception:
            pass

    def _ai_avatar() -> ft.Container:
        return ft.Container(
            content=ft.Icon(ft.Icons.SMART_TOY, size=14, color="white"),
            width=28,
            height=28,
            border_radius=14,
            bgcolor=C_ACCENT,
            alignment=ft.Alignment.CENTER,
        )

    def _user_avatar() -> ft.Container:
        return ft.Container(
            content=ft.Icon(ft.Icons.PERSON, size=14, color="white"),
            width=28,
            height=28,
            border_radius=14,
            bgcolor=C_USER_AVT,
            alignment=ft.Alignment.CENTER,
        )

    def _asst_border() -> ft.Border:
        return ft.Border(
            top=ft.BorderSide(1, C_BORDER),
            bottom=ft.BorderSide(1, C_BORDER),
            left=ft.BorderSide(1, C_BORDER),
            right=ft.BorderSide(1, C_BORDER),
        )

    def make_bubble(
        role: str,
        text: str,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
    ) -> ft.Row:
        is_user = role == "user"

        parts: list = []
        if image_base64:
            # image_base64 may be a real base64 string or a CloudFront/HTTP URL
            if image_base64.startswith("http://") or image_base64.startswith("https://"):
                data_url = image_base64
            else:
                data_url = f"data:{image_mime_type or 'image/jpeg'};base64,{image_base64}"

            def _open_lightbox(e, _url: str = data_url) -> None:
                dialog = ft.AlertDialog(
                    bgcolor="#0d0d1a",
                    content_padding=ft.Padding(left=8, right=8, top=8, bottom=8),
                    content=ft.Container(
                        content=ft.Image(src=_url, fit=ft.BoxFit.CONTAIN, expand=True),
                        width=560,
                        height=560,
                    ),
                    actions=[
                        ft.TextButton(
                            "閉じる",
                            style=ft.ButtonStyle(color=C_TEXT_DIM),
                            on_click=lambda e: page.pop_dialog(),
                        )
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                page.show_dialog(dialog)

            parts.append(
                ft.Container(
                    # width set here (not on Image) so BoxFit.CONTAIN is bounded
                    # to exactly 160px regardless of parent expand
                    width=160,
                    content=ft.Image(src=data_url, fit=ft.BoxFit.CONTAIN, border_radius=8),
                    border_radius=8,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    ink=True,
                    on_click=_open_lightbox,
                    tooltip="クリックで拡大",
                )
            )
        if text:
            parts.append(ft.Markdown(text, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB))

        inner_content = ft.Column(parts, spacing=8, tight=True) if len(parts) > 1 else parts[0]

        inner = ft.Container(
            expand=True,
            content=inner_content,
            bgcolor=C_USER_BG if is_user else C_ASST_BG,
            border_radius=ft.BorderRadius(
                top_left=16,
                top_right=16,
                bottom_left=16 if is_user else 4,
                bottom_right=4 if is_user else 16,
            ),
            border=None if is_user else _asst_border(),
            padding=ft.Padding(left=14, right=14, top=10, bottom=10),
        )
        if is_user:
            return ft.Row(
                [ft.Container(width=50), inner, _user_avatar()],
                vertical_alignment=ft.CrossAxisAlignment.END,
                spacing=10,
            )
        return ft.Row(
            [_ai_avatar(), inner, ft.Container(width=50)],
            vertical_alignment=ft.CrossAxisAlignment.END,
            spacing=10,
        )

    # ── Input bar ────────────────────────────────────────────────────────────
    image_preview_container = ft.Container(visible=False)

    async def _clear_image(e=None) -> None:
        pending_image[0] = None
        image_preview_container.visible = False
        image_preview_container.content = None
        page.update()

    file_picker = ft.FilePicker()

    _MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

    async def _pick_image(e) -> None:
        # Web mode: path is always None → use with_data=True to get file.bytes directly
        files = await file_picker.pick_files(
            allow_multiple=False,
            with_data=True,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"],
        )
        if not files or not files[0].bytes:
            return
        f = files[0]
        if len(f.bytes) > _MAX_IMAGE_BYTES:
            page.show_dialog(
                ft.SnackBar(
                    content=ft.Text("画像サイズが大きすぎます（上限 10MB）。別の画像を選んでください。", color="white"),
                    bgcolor="#b91c1c",
                    show_close_icon=True,
                )
            )
            return
        b64 = base64.b64encode(f.bytes).decode()
        ext = f.name.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
        pending_image[0] = {"base64": b64, "mime_type": mime}

        data_url = f"data:{mime};base64,{b64}"
        image_preview_container.content = ft.Container(
            content=ft.Stack(
                [
                    ft.Image(src=data_url, width=64, height=64, fit=ft.BoxFit.COVER, border_radius=8),
                    ft.Container(
                        content=ft.Icon(ft.Icons.CLOSE, size=10, color="white"),
                        width=18,
                        height=18,
                        border_radius=9,
                        bgcolor="#000000bb",
                        alignment=ft.Alignment.CENTER,
                        top=2,
                        right=2,
                        ink=True,
                        on_click=_clear_image,
                    ),
                ],
                width=64,
                height=64,
            ),
            padding=ft.Padding(left=0, right=0, top=0, bottom=8),
        )
        image_preview_container.visible = True
        page.update()

    chat_input = ft.TextField(
        hint_text="メッセージを入力… (Shift+Enter で改行)",
        hint_style=ft.TextStyle(color=C_TEXT_HNT, size=14),
        multiline=True,
        shift_enter=True,
        expand=True,
        border=ft.InputBorder.NONE,
        color=C_TEXT,
        max_lines=6,
        min_lines=1,
        content_padding=ft.Padding(left=4, right=4, top=8, bottom=8),
    )

    upload_btn = ft.Container(
        content=ft.Icon(ft.Icons.IMAGE_OUTLINED, color=C_TEXT_DIM, size=20),
        width=36,
        height=36,
        border_radius=8,
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=_pick_image,
    )

    send_btn = ft.Container(
        content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color="white", size=18),
        width=36,
        height=36,
        border_radius=8,
        bgcolor=C_ACCENT,
        alignment=ft.Alignment.CENTER,
        ink=True,
    )

    input_bar = ft.Container(
        content=ft.Container(
            content=ft.Column(
                [
                    image_preview_container,
                    ft.Row(
                        [upload_btn, chat_input, send_btn],
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=8,
                    ),
                ],
                spacing=0,
            ),
            bgcolor=C_SURFACE,
            border_radius=12,
            border=ft.Border(
                top=ft.BorderSide(1, C_BORDER),
                bottom=ft.BorderSide(1, C_BORDER),
                left=ft.BorderSide(1, C_BORDER),
                right=ft.BorderSide(1, C_BORDER),
            ),
            padding=ft.Padding(left=12, right=8, top=8, bottom=8),
        ),
        padding=ft.Padding(left=300, right=300, top=10, bottom=16),
    )

    async def handle_send(e=None) -> None:
        text = chat_input.value.strip()
        img = pending_image[0]
        if not text and not img:
            return

        chat_input.value = ""
        pending_image[0] = None
        image_preview_container.visible = False
        image_preview_container.content = None
        page.update()

        if current_chat_id[0] is None:
            try:
                new_chat_data = await api_post("/chats")
                current_chat_id[0] = new_chat_data["id"]
                await refresh_chats()
                await show_chat(skip_load=True)
                page.update()
            except Exception as ex:
                messages_lv.controls.append(ft.Text(f"エラー: {ex}", color=ft.Colors.ERROR))
                page.update()
                return

        messages_lv.controls.append(make_bubble("user", text, image_base64=img["base64"] if img else None, image_mime_type=img["mime_type"] if img else None))
        page.update()
        await _scroll_bottom(has_image=bool(img))

        # ── Typing indicator (3 dots, sequential opacity) ──────────────
        typing_dots = [
            ft.Container(
                width=8,
                height=8,
                border_radius=4,
                bgcolor=C_TEXT_DIM,
                opacity=0.25,
                animate_opacity=ft.Animation(280, ft.AnimationCurve.EASE_IN_OUT),
            )
            for _ in range(3)
        ]
        asst_inner = ft.Container(
            expand=True,
            content=ft.Row(typing_dots, spacing=7, alignment=ft.MainAxisAlignment.START),
            bgcolor=C_ASST_BG,
            border_radius=ft.BorderRadius(top_left=16, top_right=16, bottom_left=4, bottom_right=16),
            border=_asst_border(),
            padding=ft.Padding(left=16, right=16, top=15, bottom=15),
        )
        messages_lv.controls.append(
            ft.Row(
                [_ai_avatar(), asst_inner, ft.Container(width=50)],
                vertical_alignment=ft.CrossAxisAlignment.END,
                spacing=10,
            )
        )
        page.update()
        await _scroll_bottom()

        # animate dots until first text chunk arrives
        stop_anim: list[bool] = [False]

        async def _animate_dots() -> None:
            active = 0
            while not stop_anim[0]:
                for i, dot in enumerate(typing_dots):
                    dot.opacity = 1.0 if i == active else 0.25
                page.update()
                # auto_scroll=True doesn't work when items are ft.Row (Flet issue #1429)
                try:
                    await messages_lv.scroll_to(offset=-1, duration=0)
                except Exception:
                    pass
                await asyncio.sleep(0.42)
                active = (active + 1) % 3

        anim_task = asyncio.create_task(_animate_dots())

        # ── Stream response ─────────────────────────────────────────────
        asst_md = ft.Markdown("", selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)
        accumulated = ""
        first_chunk = True

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{API_BASE_URL}/chat",
                    json={
                        "message": text,
                        "chat_id": current_chat_id[0],
                        "image_base64": img["base64"] if img else None,
                        "image_mime_type": img["mime_type"] if img else None,
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if raw == "[DONE]":
                            break
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict) and parsed.get("type") == "title_update":
                            new_title = parsed.get("title", "")
                            for ch in chats:
                                if ch["id"] == parsed.get("chat_id"):
                                    ch["title"] = new_title
                            rebuild_chat_list()
                            if active_title_ctrl:
                                active_title_ctrl[0].value = new_title
                        else:
                            chunk = parsed if isinstance(parsed, str) else ""
                            if chunk:
                                if first_chunk:
                                    # swap typing dots → text
                                    stop_anim[0] = True
                                    anim_task.cancel()
                                    asst_inner.content = asst_md
                                    asst_inner.padding = ft.Padding(left=14, right=14, top=10, bottom=10)
                                    first_chunk = False
                                accumulated += chunk
                                asst_md.value = accumulated + "▌"
                        page.update()
                        try:
                            await messages_lv.scroll_to(offset=-1, duration=0)
                        except Exception:
                            pass
        except Exception:
            pass
        finally:
            stop_anim[0] = True
            anim_task.cancel()
            if accumulated:
                asst_md.value = accumulated  # remove cursor
            elif first_chunk:
                # no text arrived at all
                asst_inner.content = asst_md
                asst_md.value = "エラーが発生しました。しばらくしてから再試行してください。"
            page.update()
            await _scroll_bottom()

    chat_input.on_submit = handle_send
    send_btn.on_click = handle_send

    # ── Views ────────────────────────────────────────────────────────────────
    content_area = ft.Container(expand=True, bgcolor=C_MAIN)

    async def show_top() -> None:
        active_title_ctrl.clear()
        content_area.content = ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(
                                content=ft.Text("AI", size=22, color="white", weight=ft.FontWeight.BOLD),
                                width=60,
                                height=60,
                                border_radius=18,
                                bgcolor=C_ACCENT,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Text(
                                "AIly へようこそ",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                                color=C_TEXT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                "何でも気軽に話しかけてください",
                                size=14,
                                color=C_TEXT_DIM,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=14,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
            ],
            expand=True,
        )
        input_bar.visible = True

    async def show_chat(skip_load: bool = False) -> None:
        if not skip_load and current_chat_id[0] is not None:
            messages_lv.controls.clear()
            try:
                data = await api_get(f"/chats/{current_chat_id[0]}/messages")
                for msg in data["items"]:
                    role = "user" if msg.get("role") == "user" else "assistant"
                    image_b64: str | None = None
                    image_mime: str | None = None
                    att_url = msg.get("attachment_url")
                    att_id = msg.get("attachment_id")
                    if att_url:
                        # EKS: CloudFront URL available — use directly without fetching bytes
                        image_b64 = att_url
                        image_mime = msg.get("attachment_mime_type") or "image/jpeg"
                    elif att_id:
                        # Local: no CloudFront, proxy through API
                        try:
                            async with httpx.AsyncClient() as c:
                                r = await c.get(f"{API_BASE_URL}/attachments/{att_id}", timeout=10)
                                if r.status_code == 200:
                                    image_b64 = base64.b64encode(r.content).decode()
                                    image_mime = msg.get("attachment_mime_type") or r.headers.get("content-type", "image/jpeg")
                        except Exception:
                            pass
                    messages_lv.controls.append(make_bubble(role, msg.get("content", ""), image_base64=image_b64, image_mime_type=image_mime))
            except Exception:
                pass

        title = next(
            (ch.get("title") or "新しいチャット" for ch in chats if ch["id"] == current_chat_id[0]),
            "新しいチャット",
        )
        title_text = ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=C_TEXT, expand=True)
        active_title_ctrl.clear()
        active_title_ctrl.append(title_text)

        content_area.content = ft.Column(
            [
                ft.Container(
                    content=ft.Row([title_text]),
                    padding=ft.Padding(left=24, right=24, top=14, bottom=14),
                    border=ft.Border(bottom=ft.BorderSide(1, C_BORDER)),
                ),
                ft.Container(content=messages_lv, expand=True),
            ],
            spacing=0,
            expand=True,
        )
        input_bar.visible = True
        page.update()  # must render before scroll_to can reference the ListView
        await _scroll_bottom()

    async def show_search() -> None:
        active_title_ctrl.clear()
        input_bar.visible = False

        search_results = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=6)
        search_field = ft.TextField(
            hint_text="キーワードで検索（スペース区切りでAND検索）",
            hint_style=ft.TextStyle(color=C_TEXT_HNT, size=14),
            expand=True,
            border=ft.InputBorder.NONE,
            color=C_TEXT,
            autofocus=True,
            content_padding=ft.Padding(left=4, right=4, top=8, bottom=8),
        )

        async def do_search(e=None) -> None:
            q = search_field.value.strip()
            search_results.controls.clear()
            if not q:
                page.update()
                return
            try:
                data = await api_get(f"/chats/search?q={quote(q)}")
                items = data.get("items", [])
            except Exception:
                items = []

            if not items:
                search_results.controls.append(ft.Text("該当するチャットが見つかりませんでした。", color=C_TEXT_DIM, size=13))
            else:
                search_results.controls.append(ft.Text(f"{len(items)} 件見つかりました", size=11, color=C_TEXT_DIM))
                for item in items:

                    async def on_result(e, _id: int = item["id"]) -> None:
                        current_chat_id[0] = _id
                        rebuild_chat_list()
                        await show_chat()
                        page.update()

                    search_results.controls.append(
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=14, color=C_TEXT_DIM),
                                    ft.Text(
                                        item.get("title") or "新しいチャット",
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        color=C_TEXT,
                                        size=13,
                                        expand=True,
                                    ),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=ft.Padding(left=14, right=14, top=11, bottom=11),
                            border_radius=8,
                            bgcolor=C_SURFACE,
                            border=ft.Border(
                                top=ft.BorderSide(1, C_BORDER),
                                bottom=ft.BorderSide(1, C_BORDER),
                                left=ft.BorderSide(1, C_BORDER),
                                right=ft.BorderSide(1, C_BORDER),
                            ),
                            ink=True,
                            on_click=on_result,
                        )
                    )
            page.update()

        search_field.on_submit = do_search

        content_area.content = ft.Column(
            [
                ft.Container(
                    content=ft.Text("チャット検索", size=16, weight=ft.FontWeight.BOLD, color=C_TEXT),
                    padding=ft.Padding(left=24, right=24, top=16, bottom=14),
                    border=ft.Border(bottom=ft.BorderSide(1, C_BORDER)),
                ),
                ft.Container(
                    content=ft.Container(
                        content=ft.Row(
                            [
                                search_field,
                                ft.Container(
                                    content=ft.Icon(ft.Icons.SEARCH, color=C_TEXT_DIM, size=20),
                                    padding=ft.Padding(left=8, right=8, top=4, bottom=4),
                                    ink=True,
                                    on_click=do_search,
                                ),
                            ],
                            spacing=4,
                        ),
                        bgcolor=C_SURFACE,
                        border_radius=10,
                        border=ft.Border(
                            top=ft.BorderSide(1, C_BORDER),
                            bottom=ft.BorderSide(1, C_BORDER),
                            left=ft.BorderSide(1, C_BORDER),
                            right=ft.BorderSide(1, C_BORDER),
                        ),
                        padding=ft.Padding(left=14, right=6, top=6, bottom=6),
                    ),
                    padding=ft.Padding(left=300, right=300, top=14, bottom=14),
                ),
                ft.Container(
                    content=search_results,
                    expand=True,
                    padding=ft.Padding(left=300, right=300, top=0, bottom=16),
                ),
            ],
            spacing=0,
            expand=True,
        )

    # ── Root layout ──────────────────────────────────────────────────────────
    main_col = ft.Column(
        [content_area, input_bar],
        spacing=0,
        expand=True,
    )

    # FilePicker is a Service in Flet 0.85 — it auto-registers via
    # context.page._services; adding it to page.overlay would render it as
    # a visible control and cause "Unknown control: FilePicker".

    page.add(
        ft.Row(
            [
                sidebar,
                ft.VerticalDivider(width=1, thickness=1, color=C_BORDER),
                main_col,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    )

    await refresh_chats()
    await show_top()
    page.update()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8502))
    ft.run(main, host="0.0.0.0", port=port, view=ft.AppView.WEB_BROWSER)
