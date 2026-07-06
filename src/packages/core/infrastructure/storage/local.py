import os

from .interface import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save(self, key: str, data: bytes, mime_type: str) -> None:
        path = os.path.join(self._base_dir, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def load(self, key: str) -> bytes:
        path = os.path.join(self._base_dir, key)
        with open(path, "rb") as f:
            return f.read()
