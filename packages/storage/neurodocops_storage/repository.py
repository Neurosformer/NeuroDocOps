from __future__ import annotations

from typing import Protocol
from uuid import UUID

from packages.domain.neurodocops_domain.models import AuditEvent, ClaimPacketRecord


class PacketRepository(Protocol):
    """Persistence boundary for claim packets and audit events.

    Workflow code depends on this contract instead of a concrete database. The
    in-memory implementation is used for local tests; Postgres should implement
    the same methods without changing workflow behavior.
    """

    def add_packet(self, packet: ClaimPacketRecord) -> ClaimPacketRecord:
        ...

    def save_packet(self, packet: ClaimPacketRecord) -> ClaimPacketRecord:
        ...

    def get_packet(self, packet_id: UUID) -> ClaimPacketRecord | None:
        ...

    def list_packets(self) -> list[ClaimPacketRecord]:
        ...

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        ...

    def list_audit_events(self, packet_id: UUID | None = None) -> list[AuditEvent]:
        ...
