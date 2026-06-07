from __future__ import annotations

import os

from .memory import InMemoryPacketRepository
from .repository import PacketRepository


def create_packet_repository() -> PacketRepository:
    """Create the configured packet repository for API and worker runtime."""

    backend = os.getenv("NEURODOCOPS_STORAGE_BACKEND", "memory").strip().lower()
    if backend in {"memory", "inmemory", "in-memory"}:
        return InMemoryPacketRepository()
    if backend in {"postgres", "postgresql"}:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL must be set when NEURODOCOPS_STORAGE_BACKEND=postgres")
        from .postgres import PostgresPacketRepository

        connect_attempts = int(os.getenv("NEURODOCOPS_DB_CONNECT_ATTEMPTS", "5"))
        return PostgresPacketRepository(database_url, connect_attempts=connect_attempts)
    raise RuntimeError(f"Unsupported NEURODOCOPS_STORAGE_BACKEND: {backend}")
