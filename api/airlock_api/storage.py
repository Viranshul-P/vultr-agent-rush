"""Blob storage: Vultr Object Storage (S3 API) in production, local folder in dev."""

from __future__ import annotations

from pathlib import Path

from .config import settings


class _Local:
    kind = "local"

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("bad key")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._p(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._p(key).exists()


class _S3:
    kind = "vultr-object-storage"

    def __init__(self):
        import boto3

        self.bucket = settings.s3_bucket
        self.c = boto3.client("s3", endpoint_url=settings.s3_endpoint, aws_access_key_id=settings.s3_access_key,
                              aws_secret_access_key=settings.s3_secret_key)
        try:
            self.c.head_bucket(Bucket=self.bucket)
        except Exception:
            self.c.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.c.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def get(self, key: str) -> bytes:
        return self.c.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.c.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


store = _S3() if settings.s3_endpoint and settings.s3_access_key else _Local(settings.storage_dir)
