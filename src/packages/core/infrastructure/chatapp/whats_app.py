import base64
from typing import Any

import requests

from packages.core.config import settings
from .interface import Interface


class WhatsApp(Interface):
    _BASE_URL = f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        }

    def send_text_message(self, to: str, body: str) -> dict[str, Any]:
        url = f"{self._BASE_URL}/{settings.whatsapp_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        response = requests.post(url, headers=self._headers(), json=payload, timeout=20)
        response.raise_for_status()
        return dict(response.json())

    def get_media_url(self, media_id: str) -> str:
        url = f"{self._BASE_URL}/{media_id}"
        response = requests.get(url, headers={"Authorization": f"Bearer {settings.whatsapp_token}"}, timeout=20)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return str(data["url"])

    def download_media(self, media_id: str) -> tuple[bytes, str | None]:
        media_url = self.get_media_url(media_id)
        response = requests.get(media_url, headers={"Authorization": f"Bearer {settings.whatsapp_token}"}, timeout=60)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")

    def to_inline_data(self, data: bytes, mime_type: str | None) -> dict:
        safe_mime = mime_type or "application/octet-stream"
        return {
            "mime_type": safe_mime,
            "data": base64.b64encode(data).decode("utf-8"),
        }


client = WhatsApp()
