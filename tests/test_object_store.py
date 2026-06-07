import hashlib

import pytest

from packages.storage.neurodocops_storage import InMemoryObjectStore, create_object_store


def test_in_memory_object_store_puts_and_gets_bytes() -> None:
    store = InMemoryObjectStore(bucket="test-bucket")
    data = b"source document bytes"

    reference = store.put_bytes("packets/one/document.pdf", data, "application/pdf")

    assert reference.bucket == "test-bucket"
    assert reference.key == "packets/one/document.pdf"
    assert reference.content_type == "application/pdf"
    assert reference.size_bytes == len(data)
    assert reference.checksum_sha256 == hashlib.sha256(data).hexdigest()
    assert store.get_bytes(reference.key) == data


def test_object_store_factory_defaults_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEURODOCOPS_OBJECT_STORAGE_BACKEND", raising=False)

    store = create_object_store()

    assert isinstance(store, InMemoryObjectStore)


def test_object_store_factory_requires_minio_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEURODOCOPS_OBJECT_STORAGE_BACKEND", "minio")
    monkeypatch.delenv("OBJECT_STORAGE_ENDPOINT", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_ACCESS_KEY", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OBJECT_STORAGE_ENDPOINT"):
        create_object_store()


def test_object_store_factory_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEURODOCOPS_OBJECT_STORAGE_BACKEND", "filesystem")

    with pytest.raises(RuntimeError, match="Unsupported"):
        create_object_store()
