import pytest

from neurodocops.models import (
    AuditAction,
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
    ReviewTaskPriority,
    ReviewTaskStatus,
)
from neurodocops.service import ClaimPacketWorkflowService, ReviewTaskNotFoundError, WorkflowConflictError
from packages.providers.neurodocops_providers import ProviderRegistry, ProviderSettings
from packages.storage.neurodocops_storage import InMemoryObjectStore, InMemoryPacketRepository


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

    for task in evaluated.review_tasks:
        service.resolve_review_task(packet.id, task.id, reviewer="claims.ops@example.com", notes="Validated evidence.")

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

    audit_actions = [event.action.value for event in service.list_audit_events(packet.id)]
    assert audit_actions[:4] == [
        "packet_intaked",
        "documents_classified",
        "fields_extracted",
        "checklist_evaluated",
    ]
    assert "review_task_resolved" in audit_actions
    assert audit_actions[-2:] == ["review_completed", "packet_exported"]


def test_workflow_uses_uploaded_pdf_bytes_for_local_text_extraction() -> None:
    object_store = InMemoryObjectStore(bucket="test-documents")
    source = object_store.put_bytes(
        "claim-packets/test/source-documents/claim.pdf",
        embedded_text_pdf("Claim form with claim number CLM-PDF-WF and policy number POL-PDF-WF."),
        "application/pdf",
    )

    def load_source_bytes(document):
        return object_store.get_bytes(document.source_object.key) if document.source_object else None

    registry = ProviderRegistry(ProviderSettings(ocr_provider="local_pdf_text"), source_bytes_loader=load_source_bytes)
    service = ClaimPacketWorkflowService(provider_registry=registry, repository=InMemoryPacketRepository(), source_bytes_loader=load_source_bytes)
    packet = service.intake_packet(
        ClaimPacketCreate(
            claim_reference="CLM-PDF-WF",
            claimant_name="PDF Claimant",
            loss_type="auto",
            documents=[
                ClaimDocumentCreate(
                    filename="claim.pdf",
                    text="fallback claim number WRONG-FORM-TEXT",
                    content_type="application/pdf",
                    source_object=source,
                )
            ],
        )
    )

    extracted = service.extract_packet(packet.id)
    document = extracted.documents[0]

    assert document.document_type == DocumentType.CLAIM_FORM
    assert document.ocr_provider == "local-pdf-text"
    assert "CLM-PDF-WF" in document.ocr_text
    assert "WRONG-FORM-TEXT" not in document.ocr_text
    assert any(field.name == "claim_number" and field.value == "CLM-PDF-WF" for field in document.extracted_fields)
    assert any(field.name == "policy_number" and field.value == "POL-PDF-WF" for field in document.extracted_fields)


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


def test_packet_review_approval_requires_resolved_review_tasks() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload())
    evaluated = service.evaluate_checklist(packet.id)

    with pytest.raises(WorkflowConflictError, match="Open review tasks"):
        service.complete_review(
            packet.id,
            ReviewRequest(decision=ReviewDecision.APPROVE, reviewer="claims.ops@example.com"),
        )

    assert evaluated.review_tasks
    assert service.get_packet(packet.id).status == PacketStatus.NEEDS_REVIEW


def test_resolve_and_reopen_review_task_records_audit() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload(include_identity=False))
    evaluated = service.evaluate_checklist(packet.id)
    target_task = evaluated.review_tasks[0]

    resolved = service.resolve_review_task(packet.id, target_task.id, reviewer="reviewer@example.com", notes="Validated alternate identity evidence.")
    resolved_task = next(task for task in resolved.review_tasks if task.id == target_task.id)
    assert resolved_task.status.value == "resolved"
    assert resolved_task.resolved_at is not None
    assert resolved_task.reviewer == "reviewer@example.com"
    assert resolved_task.notes == "Validated alternate identity evidence."

    reopened = service.reopen_review_task(packet.id, target_task.id, reviewer="manager@example.com", notes="Reopened during QA check.")
    reopened_task = next(task for task in reopened.review_tasks if task.id == target_task.id)
    assert reopened_task.status.value == "open"
    assert reopened_task.resolved_at is None
    assert reopened_task.reviewer == "manager@example.com"
    assert reopened_task.notes == "Reopened during QA check."

    audit_actions = [event.action for event in service.list_audit_events(packet.id)]
    assert AuditAction.REVIEW_TASK_RESOLVED in audit_actions
    assert AuditAction.REVIEW_TASK_REOPENED in audit_actions


def test_review_queue_filters_by_assignee_priority_and_due_date() -> None:
    from datetime import datetime, timezone

    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload(include_identity=False))
    evaluated = service.evaluate_checklist(packet.id)
    task = evaluated.review_tasks[0]
    due_at = datetime(2026, 6, 10, 17, 0, tzinfo=timezone.utc)

    updated = service.update_review_task(
        packet.id,
        task.id,
        actor="manager@example.com",
        updates={"assignee": "reviewer@example.com", "priority": ReviewTaskPriority.HIGH, "due_at": due_at, "notes": "Queue triage."},
    )
    updated_task = next(candidate for candidate in updated.review_tasks if candidate.id == task.id)

    assert updated_task.assignee == "reviewer@example.com"
    assert updated_task.priority == ReviewTaskPriority.HIGH
    assert updated_task.due_at == due_at
    assert updated_task.notes == "Queue triage."
    assert service.list_review_queue(assignee="reviewer@example.com", priority=ReviewTaskPriority.HIGH)[0].task.id == task.id
    assert service.list_review_queue(assignee="other@example.com") == []
    assert service.list_review_queue(due_before=datetime(2026, 6, 11, tzinfo=timezone.utc))[0].task.id == task.id
    assert service.list_review_queue(due_before=datetime(2026, 6, 9, tzinfo=timezone.utc)) == []
    assert task.id not in {item.task.id for item in service.list_review_queue(unassigned=True)}

    audit_actions = [event.action for event in service.list_audit_events(packet.id)]
    assert AuditAction.REVIEW_TASK_ASSIGNED in audit_actions
    assert AuditAction.REVIEW_TASK_UPDATED in audit_actions


def test_resolving_assigned_review_task_preserves_queue_owner() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload(include_identity=False))
    evaluated = service.evaluate_checklist(packet.id)
    task = evaluated.review_tasks[0]

    service.update_review_task(packet.id, task.id, actor="manager@example.com", updates={"assignee": "reviewer@example.com"})
    resolved = service.resolve_review_task(packet.id, task.id, reviewer="reviewer@example.com", notes="Resolved assigned task.")
    resolved_task = next(candidate for candidate in resolved.review_tasks if candidate.id == task.id)

    assert resolved_task.assignee == "reviewer@example.com"
    assert resolved_task.reviewer == "reviewer@example.com"
    assert resolved_task.status == ReviewTaskStatus.RESOLVED


def test_resolving_unknown_review_task_raises_not_found() -> None:
    from uuid import uuid4

    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload())
    service.evaluate_checklist(packet.id)

    with pytest.raises(ReviewTaskNotFoundError):
        service.resolve_review_task(packet.id, uuid4(), reviewer="reviewer@example.com")


def test_reopening_approved_packet_blocks_export_again() -> None:
    service = ClaimPacketWorkflowService()
    packet = service.intake_packet(claim_packet_payload())
    evaluated = service.evaluate_checklist(packet.id)
    for task in evaluated.review_tasks:
        service.resolve_review_task(packet.id, task.id, reviewer="reviewer@example.com")
    reviewed = service.complete_review(
        packet.id,
        ReviewRequest(decision=ReviewDecision.APPROVE, reviewer="manager@example.com"),
    )
    assert reviewed.status == PacketStatus.APPROVED

    reopened = service.reopen_review_task(packet.id, evaluated.review_tasks[0].id, reviewer="auditor-qa@example.com", notes="Citation needs another look.")

    assert reopened.status == PacketStatus.NEEDS_REVIEW
    with pytest.raises(WorkflowConflictError, match="approved"):
        service.export_packet(packet.id)


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


def embedded_text_pdf(text: str) -> bytes:
    return f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 64 >>
stream
BT /F1 12 Tf 72 720 Td ({text}) Tj ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
trailer << /Root 1 0 R >>
%%EOF
""".encode("latin-1")
