from .interface import StorageBackend


class S3Storage(StorageBackend):
    def __init__(self, bucket: str, prefix: str) -> None:
        import boto3  # lazy import — only needed on non-local environments

        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._client = boto3.client("s3")

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}/{key}"

    def save(self, key: str, data: bytes, mime_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=self._full_key(key),
            Body=data,
            ContentType=mime_type,
        )

    def load(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=self._full_key(key))
        return response["Body"].read()
