from packages.core.config import settings

from .interface import StorageBackend
from .local import LocalStorage
from .s3 import S3Storage

__all__ = ["StorageBackend", "backend"]


def _make_backend() -> StorageBackend:
    if settings.app_env == "local":
        return LocalStorage(base_dir=settings.attachment_local_dir)
    return S3Storage(bucket=settings.ml_data_bucket, prefix=settings.attachment_s3_prefix)


backend: StorageBackend = _make_backend()
