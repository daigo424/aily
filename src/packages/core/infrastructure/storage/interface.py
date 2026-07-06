from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, mime_type: str) -> None:
        """Save bytes under the given key."""

    @abstractmethod
    def load(self, key: str) -> bytes:
        """Return bytes for the given key."""
