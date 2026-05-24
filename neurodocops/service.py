from __future__ import annotations

from uuid import UUID

from neurodocops.models import (
    AuditAction,
    AuditEvent,
    Citation,
    DocumentCreate,
    DocumentRecord,
    DocumentStatus,
    DocumentType,
    ExtractedField,
    ReviewDecision,
    ReviewRequest,
)


class DocumentNotFoundError(LookupError):
    pass


class DocumentWorkflowService:
    """In-memory MVP workflow service.

    This is intentionally infrastructure-free so product behavior can be tested
    before choosing storage, OCR, queue, and model vendors.
    """

    def __init__(self) -> None:
        self._documents: dict[UUID, DocumentRecord] = {}
        self._audit_events: list[AuditEvent] = []

    def ingest_document(self, payload: DocumentCreate) -> DocumentRecord:
        document = DocumentRecord(**payload.model_dump())
        self._documents[document.id] = document
        self._audit(document.id, AuditAction.DOCUMENT_INGESTED, detail={"filename": document.filename})
        return document

    def list_documents(self) -> list[DocumentRecord]:
        return sorted(self._documents.values(), key=lambda document: document.created_at)

    def get_document(self, document_id: UUID) -> DocumentRecord:
        try:
            return self._documents[document_id]
        except KeyError as exc:
            raise DocumentNotFoundError(str(document_id)) from exc

    def classify_document(self, document_id: UUID) -> DocumentRecord:
        document = self.get_document(document_id)
        lowered = document.text.lower()

        if any(token in lowered for token in ["claim", "policy", "incident"]):
            document.document_type = DocumentType.CLAIM_FORM
        elif any(token in lowered for token in ["invoice", "amount due", "purchase order"]):
            document.document_type = DocumentType.INVOICE
        elif any(token in lowered for token in ["agreement", "contract", "termination"]):
            document.document_type = DocumentType.CONTRACT
        elif any(token in lowered for token in ["passport", "national id", "identity"]):
            document.document_type = DocumentType.IDENTITY_DOCUMENT
        elif any(token in lowered for token in ["audit", "compliance", "regulation"]):
            document.document_type = DocumentType.COMPLIANCE_REPORT
        else:
            document.document_type = DocumentType.UNKNOWN

        document.status = DocumentStatus.CLASSIFIED
        document.touch()
        self._audit(
            document.id,
            AuditAction.DOCUMENT_CLASSIFIED,
            detail={"document_type": document.document_type.value},
        )
        return document

    def extract_fields(self, document_id: UUID) -> DocumentRecord:
        document = self.get_document(document_id)
        if document.status == DocumentStatus.INGESTED:
            self.classify_document(document_id)

        document.extracted_fields = self._extract_fields_for_type(document)
        document.status = (
            DocumentStatus.NEEDS_REVIEW
            if any(field.confidence < 0.85 for field in document.extracted_fields)
            else DocumentStatus.EXTRACTED
        )
        document.touch()
        self._audit(
            document.id,
            AuditAction.FIELDS_EXTRACTED,
            detail={"field_count": len(document.extracted_fields), "status": document.status.value},
        )
        return document

    def complete_review(self, document_id: UUID, review: ReviewRequest) -> DocumentRecord:
        document = self.get_document(document_id)
        document.status = (
            DocumentStatus.APPROVED
            if review.decision == ReviewDecision.APPROVE
            else DocumentStatus.NEEDS_REVIEW
        )
        document.touch()
        self._audit(
            document.id,
            AuditAction.REVIEW_COMPLETED,
            actor=review.reviewer,
            detail={"decision": review.decision.value, "notes": review.notes},
        )
        return document

    def list_audit_events(self, document_id: UUID | None = None) -> list[AuditEvent]:
        if document_id is None:
            return list(self._audit_events)
        return [event for event in self._audit_events if event.document_id == document_id]

    def _extract_fields_for_type(self, document: DocumentRecord) -> list[ExtractedField]:
        text = " ".join(document.text.split())
        snippet = text[:180] or document.filename
        common = [
            ExtractedField(
                name="source_filename",
                value=document.filename,
                confidence=0.99,
                citation=Citation(page=1, snippet=document.filename),
            )
        ]

        if document.document_type == DocumentType.INVOICE:
            return common + [
                ExtractedField(name="invoice_summary", value=snippet, confidence=0.72, citation=Citation(page=1, snippet=snippet))
            ]
        if document.document_type == DocumentType.CLAIM_FORM:
            return common + [
                ExtractedField(name="claim_summary", value=snippet, confidence=0.7, citation=Citation(page=1, snippet=snippet))
            ]
        if document.document_type == DocumentType.CONTRACT:
            return common + [
                ExtractedField(name="contract_summary", value=snippet, confidence=0.68, citation=Citation(page=1, snippet=snippet))
            ]
        return common + [
            ExtractedField(name="document_summary", value=snippet, confidence=0.55, citation=Citation(page=1, snippet=snippet))
        ]

    def _audit(
        self,
        document_id: UUID,
        action: AuditAction,
        actor: str = "system",
        detail: dict[str, object] | None = None,
    ) -> None:
        self._audit_events.append(
            AuditEvent(document_id=document_id, action=action, actor=actor, detail=detail or {})
        )
