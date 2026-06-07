import pytest

from neurodocops.models import (
    Citation,
    ClaimDocumentCreate,
    ClaimDocumentRecord,
    ClaimPacketCreate,
    DocumentType,
    ExtractedField,
    OCRResult,
    PacketStatus,
    ReviewDecision,
    ReviewRequest,
)
from neurodocops.service import ClaimPacketWorkflowService, WorkflowConflictError
from packages.storage.neurodocops_storage import InMemoryPacketRepository


class HighConfidenceExtractionProvider:
    def classify_document(self, document: ClaimDocumentRecord, ocr: OCRResult) -> DocumentType:
        filename = document.filename.lower()
        if "claim" in filename:
            return DocumentType.CLAIM_FORM
        if "incident" in filename:
            return DocumentType.INCIDENT_REPORT
        if "invoice" in filename:
            return DocumentType.REPAIR_INVOICE
        if "identity" in filename:
            return DocumentType.IDENTITY_DOCUMENT
        return DocumentType.UNKNOWN

    def extract_fields(self, document: ClaimDocumentRecord, ocr: OCRResult) -> list[ExtractedField]:
        return [
            ExtractedField(
                name="verified_field",
                value="verified",
                confidence=0.99,
                citation=Citation(document_id=document.id, page=1, snippet=ocr.text[:80] or document.filename),
            )
        ]


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
    assert {document.ocr_provider for document in extracted.documents} == {"mock-ocr"}
    assert all(document.ocr_text for document in extracted.documents)
    assert any(field.name == "ocr_provider" for document in extracted.documents for field in document.extracted_fields)

    evaluated = service.evaluate_checklist(packet.id)
    assert evaluated.status == PacketStatus.NEEDS_REVIEW
    assert len(evaluated.checklist) == 5
    assert all(item.status.value != "fail" for item in evaluated.checklist[:4])
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
    assert any(field.name == "claim_number" for document in export.documents for field in document.extracted_fields)
    assert any(field.name == "policy_number" for document in export.documents for field in document.extracted_fields)

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


def test_export_requires_approval() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload())

    with pytest.raises(WorkflowConflictError, match="approved"):
        service.export_packet(packet.id)


def test_export_requires_explicit_review_even_without_open_tasks() -> None:
    service = ClaimPacketWorkflowService(extraction_provider=HighConfidenceExtractionProvider())
    packet = service.intake_packet(claim_packet_payload())

    evaluated = service.evaluate_checklist(packet.id)

    assert evaluated.status == PacketStatus.NEEDS_REVIEW
    assert not evaluated.review_tasks
    with pytest.raises(WorkflowConflictError, match="approved"):
        service.export_packet(packet.id)

    reviewed = service.complete_review(
        packet.id,
        ReviewRequest(decision=ReviewDecision.APPROVE, reviewer="claims.ops@example.com"),
    )

    assert reviewed.status == PacketStatus.APPROVED
    assert service.export_packet(packet.id).status == PacketStatus.EXPORTED


def test_review_requires_checklist_evaluation() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload())

    with pytest.raises(WorkflowConflictError, match="Checklist"):
        service.complete_review(
            packet.id,
            ReviewRequest(decision=ReviewDecision.APPROVE, reviewer="claims.ops@example.com"),
        )


def test_request_changes_keeps_packet_in_review_with_open_task() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload())
    service.evaluate_checklist(packet.id)

    reviewed = service.complete_review(
        packet.id,
        ReviewRequest(decision=ReviewDecision.REQUEST_CHANGES, reviewer="claims.ops@example.com", notes="Need repair total."),
    )

    assert reviewed.status == PacketStatus.NEEDS_REVIEW
    assert any(task.status.value == "open" for task in reviewed.review_tasks)


def test_auto_loss_requires_repair_invoice() -> None:
    service = ClaimPacketWorkflowService()
    documents = [
        ClaimDocumentCreate(filename="claim-form.pdf", text="Claim form for claim number CLM-1001 and policy number POL-42."),
        ClaimDocumentCreate(filename="incident-report.pdf", text="Incident report for accident with loss date 2026-05-01."),
        ClaimDocumentCreate(filename="identity.pdf", text="Passport identity document for claimant Amina Rahman."),
    ]
    packet = service.intake_packet(
        ClaimPacketCreate(claim_reference="CLM-1001", claimant_name="Amina Rahman", loss_type="auto", documents=documents)
    )

    evaluated = service.evaluate_checklist(packet.id)

    assert any(item.required_document_type == DocumentType.REPAIR_INVOICE for item in evaluated.checklist if item.status.value == "fail")


def test_workflow_service_uses_injected_packet_repository() -> None:
    repository = InMemoryPacketRepository()
    intake_service = ClaimPacketWorkflowService(repository=repository)
    review_service = ClaimPacketWorkflowService(repository=repository)

    packet = intake_service.intake_packet(claim_packet_payload())
    evaluated = review_service.evaluate_checklist(packet.id)

    assert evaluated.id == packet.id
    assert review_service.get_packet(packet.id).status == PacketStatus.NEEDS_REVIEW
    assert [event.action.value for event in review_service.list_audit_events(packet.id)] == [
        "packet_intaked",
        "documents_classified",
        "fields_extracted",
        "checklist_evaluated",
    ]
