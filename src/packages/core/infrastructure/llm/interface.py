from abc import ABC, abstractmethod
from typing import Any


class Interface(ABC):
    @abstractmethod
    def gen_json(self, prompt: str, schema: dict[str, Any], temperature: float = 0.1) -> dict[str, Any]:
        pass

    @abstractmethod
    def gen_content_from_image(self, image_bytes: bytes, mime_type: str | None) -> str:
        pass

    @abstractmethod
    def gen_content_from_audio(self, audio_bytes: bytes, mime_type: str | None) -> str:
        pass
