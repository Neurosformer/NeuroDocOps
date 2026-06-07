import pytest

from packages.storage.neurodocops_storage import InMemoryPacketRepository, create_packet_repository


def test_repository_factory_defaults_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEURODOCOPS_STORAGE_BACKEND", raising=False)

    repository = create_packet_repository()

    assert isinstance(repository, InMemoryPacketRepository)


def test_repository_factory_requires_database_url_for_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEURODOCOPS_STORAGE_BACKEND", "postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_packet_repository()


def test_repository_factory_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEURODOCOPS_STORAGE_BACKEND", "sqlite")

    with pytest.raises(RuntimeError, match="Unsupported"):
        create_packet_repository()
