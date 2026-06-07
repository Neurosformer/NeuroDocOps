import os

import pytest

from neurodocops.models import AuditAction, AuditEvent, ClaimDocumentCreate, ClaimPacketCreate, PacketStatus, SourceObjectRef
from neurodocops.service import ClaimPacketWorkflowService
from packages.storage.neurodocops_storage import InMemoryPacketRepository


def packet_payload(reference: str = "CLM-STORE-1") -> ClaimPacketCreate:
    return ClaimPacketCreate(
        claim_reference=reference,
        claimant_name="Repository Tester",
        loss_type="auto",
        documents=[
            ClaimDocumentCreate(
                filename="claim-form.pdf",
                text=f"Claim form claim number {reference} policy number P-STORE.",
                source_object=SourceObjectRef(
                    bucket="contract-bucket",
                    key=f"claim-packets/{reference}/claim-form.pdf",
                    content_type="application/pdf",
                    size_bytes=12,
                    checksum_sha256="a" * 64,
                ),
            ),
            ClaimDocumentCreate(filename="incident.pdf", text="Incident report with loss date 2026-05-01."),
            ClaimDocumentCreate(filename="identity.pdf", text="Passport identity document for Repository Tester."),
            ClaimDocumentCreate(filename="invoice.pdf", text="Repair invoice amount due 500 USD."),
        ],
    )


def assert_packet_repository_contract(repository) -> None:
    service = ClaimPacketWorkflowService(repository=repository)
    packet = service.intake_packet(packet_payload())

    assert repository.get_packet(packet.id).claim_reference == "CLM-STORE-1"
    assert repository.get_packet(packet.id).status == PacketStatus.INTAKED
    assert repository.get_packet(packet.id).documents[0].id == packet.documents[0].id
    assert repository.get_packet(packet.id).documents[0].source_object.key == f"claim-packets/{packet.claim_reference}/claim-form.pdf"
    assert repository.get_packet(packet.id).created_at == packet.created_at

    evaluated = service.evaluate_checklist(packet.id)
    assert repository.get_packet(packet.id).status == PacketStatus.NEEDS_REVIEW
    assert repository.get_packet(packet.id).checklist
    assert repository.get_packet(packet.id).review_tasks
    assert repository.get_packet(packet.id).documents[0].extracted_fields
    assert repository.list_packets()[0].id == evaluated.id

    other = service.intake_packet(packet_payload("CLM-STORE-2"))
    all_packets = repository.list_packets()
    assert [stored.id for stored in all_packets] == [packet.id, other.id]

    manual_event = AuditEvent(packet_id=packet.id, action=AuditAction.PACKET_EXPORTED, detail={"contract": True})
    repository.add_audit_event(manual_event)
    packet_events = repository.list_audit_events(packet.id)
    assert manual_event.id in {event.id for event in packet_events}
    assert all(event.packet_id == packet.id for event in packet_events)
    assert len(repository.list_audit_events()) > len(packet_events)


def test_in_memory_packet_repository_contract() -> None:
    assert_packet_repository_contract(InMemoryPacketRepository())


@pytest.mark.skipif(
    not os.getenv("NEURODOCOPS_TEST_DATABASE_URL"),
    reason="set NEURODOCOPS_TEST_DATABASE_URL to run Postgres repository integration test",
)
def test_postgres_packet_repository_contract() -> None:
    from packages.storage.neurodocops_storage.postgres import PostgresPacketRepository

    repository = PostgresPacketRepository(os.environ["NEURODOCOPS_TEST_DATABASE_URL"])
    with repository._connect() as connection:
        connection.execute("delete from audit_events")
        connection.execute("delete from claim_packets")
    assert_packet_repository_contract(repository)
