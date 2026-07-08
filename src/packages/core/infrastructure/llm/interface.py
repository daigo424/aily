from abc import ABC, abstractmethod
from typing import Any


class Interface(ABC):
    @abstractmethod
    def gen_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def gen_content_from_image(self, image_bytes: bytes, mime_type: str | None) -> str:
        pass

    @abstractmethod
    def gen_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        system_prompt: str | None = None,
        history: list[dict] | None = None,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
    ) -> str:
        pass
