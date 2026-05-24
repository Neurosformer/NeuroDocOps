from neurodocops.models import ClaimDocumentCreate, ClaimPacketCreate, DocumentType, PacketStatus, ReviewDecision, ReviewRequest
from neurodocops.service import ClaimPacketWorkflowService


def claim_packet_payload(include_identity: bool = True) -> ClaimPacketCreate:
    documents = [
        ClaimDocumentCreate(
            filename="claim-form.pdf",
            text="Claim form for claim number CLM-1001 and policy number POL-42.",
        ),
        ClaimDocumentCreate(
            filename="incident-report.pdf",
            text="Incident report for accident with loss date 2026-05-01.",
        ),
        ClaimDocumentCreate(
            filename="repair-invoice.pdf",
            text="Repair invoice for vehicle damage. Amount due 1250 USD.",
        ),
    ]
    if include_identity:
        documents.append(
            ClaimDocumentCreate(
                filename="identity.pdf",
                text="Passport identity document for claimant Amina Rahman.",
            )
        )
    return ClaimPacketCreate(
        claim_reference="CLM-1001",
        claimant_name="Amina Rahman",
        loss_type="auto",
        documents=documents,
    )


def test_claim_packet_workflow_routes_low_confidence_fields_to_review() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload())

    assert packet.status == PacketStatus.INTAKED
    assert len(packet.documents) == 4

    classified = service.classify_documents(packet.id)
    assert [document.document_type for document in classified.documents] == [
        DocumentType.CLAIM_FORM,
        DocumentType.INCIDENT_REPORT,
        DocumentType.REPAIR_INVOICE,
        DocumentType.IDENTITY_DOCUMENT,
    ]

    extracted = service.extract_packet(packet.id)
    assert extracted.status == PacketStatus.EXTRACTED
    assert all(document.extracted_fields for document in extracted.documents)

    evaluated = service.evaluate_checklist(packet.id)
    assert evaluated.status == PacketStatus.NEEDS_REVIEW
    assert len(evaluated.checklist) == 4
    assert all(item.status.value != "fail" for item in evaluated.checklist[:3])
    assert evaluated.review_tasks

    reviewed = service.complete_review(
        packet.id,
        ReviewRequest(decision=ReviewDecision.APPROVE, reviewer="claims.ops@example.com", notes="Validated evidence."),
    )
    assert reviewed.status == PacketStatus.APPROVED
    assert all(task.status.value == "resolved" for task in reviewed.review_tasks)

    export = service.export_packet(packet.id)
    assert export.status == PacketStatus.EXPORTED
    assert export.claim_reference == "CLM-1001"
    assert export.open_review_tasks == 0
    assert "claim_form.claim_summary" in export.fields

    audit_events = service.list_audit_events(packet.id)
    assert [event.action.value for event in audit_events] == [
        "packet_intaked",
        "documents_classified",
        "fields_extracted",
        "checklist_evaluated",
        "review_completed",
        "packet_exported",
    ]


def test_missing_identity_document_creates_checklist_review_task() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload(include_identity=False))

    evaluated = service.evaluate_checklist(packet.id)

    failed_items = [item for item in evaluated.checklist if item.status.value == "fail"]
    assert len(failed_items) == 1
    assert failed_items[0].required_document_type == DocumentType.IDENTITY_DOCUMENT
    assert any("Claimant identity evidence present" in task.reason for task in evaluated.review_tasks)
