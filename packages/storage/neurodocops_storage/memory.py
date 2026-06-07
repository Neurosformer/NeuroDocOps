from __future__ import annotations

from uuid import UUID

from packages.domain.neurodocops_domain.models import AuditEvent, ClaimPacketRecord


class InMemoryPacketRepository:
    """Process-local repository used for tests and local demo runs."""

    def __init__(self) -> None:
        self._packets: dict[UUID, ClaimPacketRecord] = {}
        self._audit_events: list[AuditEvent] = []

    def add_packet(self, packet: ClaimPacketRecord) -> ClaimPacketRecord:
        self._packets[packet.id] = packet
        return packet

    def save_packet(self, packet: ClaimPacketRecord) -> ClaimPacketRecord:
        self._packets[packet.id] = packet
        return packet

    def get_packet(self, packet_id: UUID) -> ClaimPacketRecord | None:
        return self._packets.get(packet_id)

    def list_packets(self) -> list[ClaimPacketRecord]:
        return sorted(self._packets.values(), key=lambda packet: packet.created_at)

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        self._audit_events.append(event)
        return event

    def list_audit_events(self, packet_id: UUID | None = None) -> list[AuditEvent]:
        if packet_id is None:
            return list(self._audit_events)
        return [event for event in self._audit_events if event.packet_id == packet_id]
