from __future__ import annotations

import time
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from packages.domain.neurodocops_domain.models import AuditEvent, ClaimPacketRecord


class PostgresPacketRepository:
    """Postgres-backed packet repository using JSONB domain snapshots."""

    def __init__(self, database_url: str, *, initialize: bool = True, connect_attempts: int = 5) -> None:
        if not database_url:
            raise ValueError("database_url is required for PostgresPacketRepository")
        self._database_url = database_url
        self._connect_attempts = max(connect_attempts, 1)
        if initialize:
            self.initialize_schema()

    def add_packet(self, packet: ClaimPacketRecord) -> ClaimPacketRecord:
        with self._connect() as connection:
            connection.execute(
                """
                insert into claim_packets (id, claim_reference, status, created_at, updated_at, payload)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                    claim_reference = excluded.claim_reference,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                self._packet_params(packet),
            )
        return packet

    def save_packet(self, packet: ClaimPacketRecord) -> ClaimPacketRecord:
        with self._connect() as connection:
            connection.execute(
                """
                update claim_packets
                set claim_reference = %s,
                    status = %s,
                    created_at = %s,
                    updated_at = %s,
                    payload = %s
                where id = %s
                """,
                (
                    packet.claim_reference,
                    packet.status.value,
                    packet.created_at,
                    packet.updated_at,
                    Jsonb(packet.model_dump(mode="json")),
                    packet.id,
                ),
            )
        return packet

    def get_packet(self, packet_id: UUID) -> ClaimPacketRecord | None:
        with self._connect() as connection:
            row = connection.execute("select payload from claim_packets where id = %s", (packet_id,)).fetchone()
        if row is None:
            return None
        return ClaimPacketRecord.model_validate(row["payload"])

    def list_packets(self) -> list[ClaimPacketRecord]:
        with self._connect() as connection:
            rows = connection.execute("select payload from claim_packets order by created_at asc, id asc").fetchall()
        return [ClaimPacketRecord.model_validate(row["payload"]) for row in rows]

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        with self._connect() as connection:
            connection.execute(
                """
                insert into audit_events (id, packet_id, action, created_at, payload)
                values (%s, %s, %s, %s, %s)
                on conflict (id) do nothing
                """,
                (event.id, event.packet_id, event.action.value, event.created_at, Jsonb(event.model_dump(mode="json"))),
            )
        return event

    def list_audit_events(self, packet_id: UUID | None = None) -> list[AuditEvent]:
        with self._connect() as connection:
            if packet_id is None:
                rows = connection.execute("select payload from audit_events order by created_at asc, id asc").fetchall()
            else:
                rows = connection.execute(
                    "select payload from audit_events where packet_id = %s order by created_at asc, id asc",
                    (packet_id,),
                ).fetchall()
        return [AuditEvent.model_validate(row["payload"]) for row in rows]

    def health_check(self) -> bool:
        with self._connect() as connection:
            connection.execute("select 1").fetchone()
        return True

    def initialize_schema(self) -> None:
        last_error: Exception | None = None
        for attempt in range(self._connect_attempts):
            try:
                with self._connect() as connection:
                    connection.execute(
                        """
                        create table if not exists claim_packets (
                            id uuid primary key,
                            claim_reference text not null,
                            status text not null,
                            created_at timestamptz not null,
                            updated_at timestamptz not null,
                            payload jsonb not null
                        )
                        """
                    )
                    connection.execute(
                        """
                        create table if not exists audit_events (
                            id uuid primary key,
                            packet_id uuid not null,
                            action text not null,
                            created_at timestamptz not null,
                            payload jsonb not null
                        )
                        """
                    )
                    connection.execute("create index if not exists idx_claim_packets_status on claim_packets(status)")
                    connection.execute("create index if not exists idx_claim_packets_created_at on claim_packets(created_at)")
                    connection.execute("create index if not exists idx_audit_events_packet_id on audit_events(packet_id)")
                    connection.execute("create index if not exists idx_audit_events_created_at on audit_events(created_at)")
                return
            except psycopg.OperationalError as exc:
                last_error = exc
                if attempt == self._connect_attempts - 1:
                    break
                time.sleep(1)
        if last_error is not None:
            raise last_error

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def _packet_params(self, packet: ClaimPacketRecord) -> tuple[UUID, str, str, object, object, Jsonb]:
        return (
            packet.id,
            packet.claim_reference,
            packet.status.value,
            packet.created_at,
            packet.updated_at,
            Jsonb(packet.model_dump(mode="json")),
        )
