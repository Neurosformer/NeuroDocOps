from __future__ import annotations

from io import BytesIO
from hashlib import sha256
from urllib.parse import urlparse

from minio import Minio

from packages.domain.neurodocops_domain.models import SourceObjectRef


class MinioObjectStore:
    """S3-compatible object store for source document bytes."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ) -> None:
        if not endpoint or not access_key or not secret_key or not bucket:
            raise RuntimeError("MinIO object storage requires endpoint, access key, secret key, and bucket")
        parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
        self._bucket = bucket
        self._client = Minio(
            parsed.netloc or parsed.path,
            access_key=access_key,
            secret_key=secret_key,
            secure=parsed.scheme == "https",
            region=region,
        )
        self._ensure_bucket()

    def put_bytes(self, key: str, data: bytes, content_type: str) -> SourceObjectRef:
        result = self._client.put_object(
            self._bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return SourceObjectRef(
            bucket=self._bucket,
            key=key,
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=sha256(data).hexdigest(),
            etag=result.etag,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def health_check(self) -> bool:
        self._client.bucket_exists(self._bucket)
        return True

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
