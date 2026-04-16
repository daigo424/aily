import json
from typing import Any, cast

from google import genai
from google.genai import types

from packages.core.config import settings

from .interface import Interface


class Gemini(Interface):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def gen_json(self, prompt: str, schema: dict[str, Any], temperature: float = 0.1) -> Any:
        response = self.client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema,
                temperature=temperature,
            ),
        )
        return json.loads(response.text or "{}")

    def gen_content_from_image(self, image_bytes: bytes, mime_type: str | None) -> str:
        prompt = (
            "画像に文字が書かれているなら、その文字をそのまま抽出してください。画像内の文字だけを返し、余計な説明は不要です。文字が読めない場合は空文字を返してください。"
        )
        response = self.client.models.generate_content(
            model=settings.gemini_model,
            contents=cast(Any, [prompt, types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg")]),
            config=types.GenerateContentConfig(temperature=0.0),
        )
        return (response.text or "").strip()

    def gen_content_from_audio(self, audio_bytes: bytes, mime_type: str | None) -> str:
        prompt = "この音声を日本語で文字起こししてください。予約内容の抽出に使うので、話された文をできるだけそのまま返してください。"
        response = self.client.models.generate_content(
            model=settings.gemini_model,
            contents=cast(Any, [prompt, types.Part.from_bytes(data=audio_bytes, mime_type=mime_type or "audio/mpeg")]),
            config=types.GenerateContentConfig(temperature=0.0),
        )
        return (response.text or "").strip()


client = Gemini(api_key=settings.gemini_api_key)
