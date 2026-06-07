from __future__ import annotations

from hashlib import sha256

from packages.domain.neurodocops_domain.models import SourceObjectRef


class InMemoryObjectStore:
    """Process-local object store for tests and local single-process runs."""

    def __init__(self, bucket: str = "memory-source-documents") -> None:
        self._bucket = bucket
        self._objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str) -> SourceObjectRef:
        self._objects[key] = data
        checksum = sha256(data).hexdigest()
        return SourceObjectRef(
            bucket=self._bucket,
            key=key,
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=checksum,
            etag=checksum,
        )

    def get_bytes(self, key: str) -> bytes:
        return self._objects[key]

    def health_check(self) -> bool:
        return True
