from __future__ import annotations

from uuid import UUID

from neurodocops.models import (
    AuditAction,
    AuditEvent,
    ChecklistItem,
    ChecklistStatus,
    Citation,
    ClaimDocumentRecord,
    ClaimPacketCreate,
    ClaimPacketRecord,
    DocumentType,
    ExportSummary,
    ExtractedField,
    PacketStatus,
    ReviewDecision,
    ReviewRequest,
    ReviewTask,
    ReviewTaskStatus,
    utc_now,
)


class PacketNotFoundError(LookupError):
    pass


class ClaimPacketWorkflowService:
    """In-memory insurance claims packet workflow service."""

    def __init__(self) -> None:
        self._packets: dict[UUID, ClaimPacketRecord] = {}
        self._audit_events: list[AuditEvent] = []

    def intake_packet(self, payload: ClaimPacketCreate) -> ClaimPacketRecord:
        packet = ClaimPacketRecord(
            claim_reference=payload.claim_reference,
            claimant_name=payload.claimant_name,
            loss_type=payload.loss_type,
            metadata=payload.metadata,
            documents=[ClaimDocumentRecord(**document.model_dump()) for document in payload.documents],
        )
        self._packets[packet.id] = packet
        self._audit(packet.id, AuditAction.PACKET_INTAKED, detail={"claim_reference": packet.claim_reference})
        return packet

    def list_packets(self) -> list[ClaimPacketRecord]:
        return sorted(self._packets.values(), key=lambda packet: packet.created_at)

    def get_packet(self, packet_id: UUID) -> ClaimPacketRecord:
        try:
            return self._packets[packet_id]
        except KeyError as exc:
            raise PacketNotFoundError(str(packet_id)) from exc

    def classify_documents(self, packet_id: UUID) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        for document in packet.documents:
            document.document_type = self._classify_document(document.text)
        packet.status = PacketStatus.CLASSIFIED
        packet.touch()
        self._audit(
            packet.id,
            AuditAction.DOCUMENTS_CLASSIFIED,
            detail={"document_types": [document.document_type.value for document in packet.documents]},
        )
        return packet

    def extract_packet(self, packet_id: UUID) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        if packet.status == PacketStatus.INTAKED:
            self.classify_documents(packet_id)

        for document in packet.documents:
            document.extracted_fields = self._extract_fields(document)

        packet.status = PacketStatus.EXTRACTED
        packet.touch()
        self._audit(packet.id, AuditAction.FIELDS_EXTRACTED, detail={"field_count": self._field_count(packet)})
        return packet

    def evaluate_checklist(self, packet_id: UUID) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        if packet.status in {PacketStatus.INTAKED, PacketStatus.CLASSIFIED}:
            self.extract_packet(packet_id)

        packet.checklist = self._build_claim_checklist(packet)
        packet.review_tasks = self._build_review_tasks(packet)
        packet.status = PacketStatus.NEEDS_REVIEW if packet.review_tasks else PacketStatus.APPROVED
        packet.touch()
        self._audit(
            packet.id,
            AuditAction.CHECKLIST_EVALUATED,
            detail={"open_review_tasks": len(packet.review_tasks), "status": packet.status.value},
        )
        return packet

    def complete_review(self, packet_id: UUID, review: ReviewRequest) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        for task in packet.review_tasks:
            if task.status == ReviewTaskStatus.OPEN:
                task.status = ReviewTaskStatus.RESOLVED
                task.resolved_at = utc_now()
                task.reviewer = review.reviewer
                task.notes = review.notes

        packet.status = PacketStatus.APPROVED if review.decision == ReviewDecision.APPROVE else PacketStatus.NEEDS_REVIEW
        packet.touch()
        self._audit(
            packet.id,
            AuditAction.REVIEW_COMPLETED,
            actor=review.reviewer,
            detail={"decision": review.decision.value, "notes": review.notes},
        )
        return packet

    def export_packet(self, packet_id: UUID) -> ExportSummary:
        packet = self.get_packet(packet_id)
        fields = {
            f"{document.document_type.value}.{field.name}": field.value
            for document in packet.documents
            for field in document.extracted_fields
        }
        packet.status = PacketStatus.EXPORTED
        packet.touch()
        self._audit(packet.id, AuditAction.PACKET_EXPORTED, detail={"field_count": len(fields)})
        return ExportSummary(
            packet_id=packet.id,
            claim_reference=packet.claim_reference,
            status=packet.status,
            document_count=len(packet.documents),
            checklist_passed=sum(item.status == ChecklistStatus.PASS for item in packet.checklist),
            checklist_failed=sum(item.status == ChecklistStatus.FAIL for item in packet.checklist),
            open_review_tasks=sum(task.status == ReviewTaskStatus.OPEN for task in packet.review_tasks),
            fields=fields,
        )

    def list_audit_events(self, packet_id: UUID | None = None) -> list[AuditEvent]:
        if packet_id is None:
            return list(self._audit_events)
        return [event for event in self._audit_events if event.packet_id == packet_id]

    def _classify_document(self, text: str) -> DocumentType:
        lowered = text.lower()
        if any(token in lowered for token in ["claim form", "claim number", "policy number"]):
            return DocumentType.CLAIM_FORM
        if any(token in lowered for token in ["medical bill", "clinic", "hospital", "treatment"]):
            return DocumentType.MEDICAL_BILL
        if any(token in lowered for token in ["repair invoice", "amount due", "invoice"]):
            return DocumentType.REPAIR_INVOICE
        if any(token in lowered for token in ["passport", "national id", "identity", "driver license"]):
            return DocumentType.IDENTITY_DOCUMENT
        if any(token in lowered for token in ["incident report", "accident", "loss date"]):
            return DocumentType.INCIDENT_REPORT
        if any(token in lowered for token in ["policy schedule", "coverage", "deductible"]):
            return DocumentType.POLICY_DOCUMENT
        return DocumentType.UNKNOWN

    def _extract_fields(self, document: ClaimDocumentRecord) -> list[ExtractedField]:
        text = " ".join(document.text.split())
        snippet = text[:180] or document.filename
        common = [
            ExtractedField(
                name="source_filename",
                value=document.filename,
                confidence=0.99,
                citation=Citation(document_id=document.id, page=1, snippet=document.filename),
            )
        ]
        field_name_by_type = {
            DocumentType.CLAIM_FORM: "claim_summary",
            DocumentType.MEDICAL_BILL: "medical_bill_summary",
            DocumentType.REPAIR_INVOICE: "repair_invoice_summary",
            DocumentType.IDENTITY_DOCUMENT: "identity_summary",
            DocumentType.INCIDENT_REPORT: "incident_summary",
            DocumentType.POLICY_DOCUMENT: "policy_summary",
            DocumentType.UNKNOWN: "document_summary",
        }
        confidence = 0.78 if document.document_type != DocumentType.UNKNOWN else 0.52
        return common + [
            ExtractedField(
                name=field_name_by_type[document.document_type],
                value=snippet,
                confidence=confidence,
                citation=Citation(document_id=document.id, page=1, snippet=snippet),
            )
        ]

    def _build_claim_checklist(self, packet: ClaimPacketRecord) -> list[ChecklistItem]:
        present_types = {document.document_type for document in packet.documents}
        required = [
            (DocumentType.CLAIM_FORM, "Claim form present"),
            (DocumentType.IDENTITY_DOCUMENT, "Claimant identity evidence present"),
            (DocumentType.INCIDENT_REPORT, "Incident or loss report present"),
        ]
        checklist = [
            ChecklistItem(
                name=name,
                required_document_type=document_type,
                status=ChecklistStatus.PASS if document_type in present_types else ChecklistStatus.FAIL,
                detail="Evidence found" if document_type in present_types else "Required evidence missing",
            )
            for document_type, name in required
        ]
        low_confidence = any(field.confidence < 0.85 for document in packet.documents for field in document.extracted_fields)
        checklist.append(
            ChecklistItem(
                name="Field confidence review",
                status=ChecklistStatus.NEEDS_REVIEW if low_confidence else ChecklistStatus.PASS,
                detail="One or more extracted fields need reviewer validation" if low_confidence else "All fields are high confidence",
            )
        )
        return checklist

    def _build_review_tasks(self, packet: ClaimPacketRecord) -> list[ReviewTask]:
        tasks = [
            ReviewTask(reason=f"Checklist failed: {item.name}")
            for item in packet.checklist
            if item.status == ChecklistStatus.FAIL
        ]
        for document in packet.documents:
            for field in document.extracted_fields:
                if field.confidence < 0.85:
                    tasks.append(
                        ReviewTask(
                            document_id=document.id,
                            reason=f"Validate low-confidence field: {field.name}",
                        )
                    )
        return tasks

    def _field_count(self, packet: ClaimPacketRecord) -> int:
        return sum(len(document.extracted_fields) for document in packet.documents)

    def _audit(
        self,
        packet_id: UUID,
        action: AuditAction,
        actor: str = "system",
        detail: dict[str, object] | None = None,
    ) -> None:
        self._audit_events.append(AuditEvent(packet_id=packet_id, action=action, actor=actor, detail=detail or {}))
