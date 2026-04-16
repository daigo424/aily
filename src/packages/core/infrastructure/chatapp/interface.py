from abc import ABC, abstractmethod


class Interface(ABC):
    @abstractmethod
    def send_text_message(self, to: str, body: str) -> dict:
        pass

    @abstractmethod
    def get_media_url(self, media_id: str) -> str:
        pass

    @abstractmethod
    def download_media(self, media_id: str) -> tuple[bytes, str | None]:
        pass

    @abstractmethod
    def to_inline_data(self, data: bytes, mime_type: str | None) -> dict:
        pass
