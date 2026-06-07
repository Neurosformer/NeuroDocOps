from __future__ import annotations

import os

from .memory_object_store import InMemoryObjectStore
from .object_store import ObjectStore


def create_object_store() -> ObjectStore:
    """Create the configured object store for API/runtime uploads."""

    backend = os.getenv("NEURODOCOPS_OBJECT_STORAGE_BACKEND", "memory").strip().lower()
    if backend in {"memory", "inmemory", "in-memory"}:
        return InMemoryObjectStore(os.getenv("OBJECT_STORAGE_BUCKET", "memory-source-documents"))
    if backend in {"minio", "s3"}:
        endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT")
        bucket = os.getenv("OBJECT_STORAGE_BUCKET")
        access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY")
        secret_key = os.getenv("OBJECT_STORAGE_SECRET_KEY")
        if not endpoint or not bucket or not access_key or not secret_key:
            raise RuntimeError("MinIO object storage requires OBJECT_STORAGE_ENDPOINT, OBJECT_STORAGE_BUCKET, OBJECT_STORAGE_ACCESS_KEY, and OBJECT_STORAGE_SECRET_KEY")
        from .minio_object_store import MinioObjectStore

        return MinioObjectStore(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            region=os.getenv("OBJECT_STORAGE_REGION", "us-east-1"),
        )
    raise RuntimeError(f"Unsupported NEURODOCOPS_OBJECT_STORAGE_BACKEND: {backend}")
