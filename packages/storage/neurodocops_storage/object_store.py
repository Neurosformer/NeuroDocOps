from __future__ import annotations

from typing import Protocol

from packages.domain.neurodocops_domain.models import SourceObjectRef


class ObjectStore(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> SourceObjectRef:
        """Store object bytes and return durable object metadata."""

    def get_bytes(self, key: str) -> bytes:
        """Return object bytes for internal tests and future OCR workers."""

    def health_check(self) -> bool:
        """Return True when the object storage dependency is reachable."""
