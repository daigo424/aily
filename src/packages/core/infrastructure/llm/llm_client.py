import base64
import json
from typing import Any

import httpx
from openai import OpenAI

from packages.core.config import settings

from .interface import Interface


def _make_strict(schema: Any) -> Any:
    if isinstance(schema, dict):
        if "properties" in schema:
            schema["additionalProperties"] = False
            schema["required"] = list(schema["properties"].keys())
        for value in schema.values():
            _make_strict(value)
    elif isinstance(schema, list):
        for item in schema:
            _make_strict(item)
    return schema


def _init_tracing() -> None:
    if not settings.langfuse_public_key or not settings.langfuse_host:
        return
    credentials = base64.b64encode(f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()).decode()
    from traceloop.sdk import Traceloop  # type: ignore[import-untyped]

    Traceloop.init(
        app_name="aily",
        api_endpoint=f"{settings.langfuse_host}/api/public/otel",
        headers={"Authorization": f"Basic {credentials}"},
        suppress_content_tracing=True,
    )


_init_tracing()


class LLMClient(Interface):
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.client = OpenAI(api_key=api_key, **({"base_url": base_url} if base_url else {}))
        self.model = model

    def _is_ollama(self) -> bool:
        url = str(self.client.base_url).lower()
        return "ollama" in url or ":11434" in url

    def _ollama_base(self) -> str:
        """Ollama base URL without /v1 suffix, for native /api/chat calls."""
        url = str(self.client.base_url).rstrip("/")
        return url[:-3] if url.endswith("/v1") else url

    def gen_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> Any:
        strict_schema = _make_strict(json.loads(json.dumps(schema)))

        if self._is_ollama() and image_base64:
            # Ollama's OpenAI compat layer splits text+image_url into separate messages,
            # causing the model to lose context. Use the native /api/chat endpoint instead,
            # which keeps text and images together in a single message via the `images` field.
            msgs: list[dict] = []
            if system_prompt:
                msgs.append({"role": "system", "content": system_prompt})
            if history:
                msgs.extend(history)
            msgs.append({"role": "user", "content": prompt, "images": [image_base64]})
            resp = httpx.post(
                f"{self._ollama_base()}/api/chat",
                json={
                    "model": self.model,
                    "messages": msgs,
                    "format": strict_schema,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return json.loads(resp.json()["message"]["content"] or "{}")

        if self._is_ollama():
            response_format = {"type": "json_schema", "json_schema": {"schema": strict_schema}}
        else:
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": strict_schema, "strict": True},
            }

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)

        if image_base64:
            data_url = f"data:{image_mime_type or 'image/jpeg'};base64,{image_base64}"
            content: str | list = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        else:
            content = prompt
        messages.append({"role": "user", "content": content})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format=response_format,
        )
        return json.loads(response.choices[0].message.content or "{}")

    def gen_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        system_prompt: str | None = None,
        history: list[dict] | None = None,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
    ) -> str:
        if self._is_ollama() and image_base64:
            msgs: list[dict] = []
            if system_prompt:
                msgs.append({"role": "system", "content": system_prompt})
            if history:
                msgs.extend(history)
            msgs.append({"role": "user", "content": prompt, "images": [image_base64]})
            resp = httpx.post(
                f"{self._ollama_base()}/api/chat",
                json={
                    "model": self.model,
                    "messages": msgs,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return (resp.json()["message"]["content"] or "").strip()

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        if image_base64:
            data_url = f"data:{image_mime_type or 'image/jpeg'};base64,{image_base64}"
            content: str | list = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        else:
            content = prompt
        messages.append({"role": "user", "content": content})
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()

    def gen_content_from_image(self, image_bytes: bytes, mime_type: str | None) -> str:
        b64 = base64.b64encode(image_bytes).decode()

        if self._is_ollama():
            resp = httpx.post(
                f"{self._ollama_base()}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "画像に文字が書かれているなら、その文字をそのまま抽出してください。"
                            "画像内の文字だけを返し、余計な説明は不要です。"
                            "文字が読めない場合は空文字を返してください。",
                            "images": [b64],
                        }
                    ],
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return (resp.json()["message"]["content"] or "").strip()

        data_url = f"data:{mime_type or 'image/jpeg'};base64,{b64}"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "画像に文字が書かれているなら、その文字をそのまま抽出してください。"
                            "画像内の文字だけを返し、余計な説明は不要です。"
                            "文字が読めない場合は空文字を返してください。",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.0,
        )
        return (response.choices[0].message.content or "").strip()


openai_client = LLMClient(api_key=settings.llm_api_key, model=settings.llm_model)

vllm_client = LLMClient(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model,
)
