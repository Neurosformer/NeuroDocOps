from __future__ import annotations

from uuid import UUID

from neurodocops.models import (
    AuditAction,
    AuditEvent,
    ChecklistItem,
    ChecklistStatus,
    ClaimDocumentRecord,
    ClaimPacketCreate,
    ClaimPacketRecord,
    DocumentType,
    ExportSummary,
    PacketStatus,
    ReviewDecision,
    ReviewRequest,
    ReviewTask,
    ReviewTaskStatus,
    utc_now,
)
from neurodocops.models import OCRResult
from neurodocops.providers import ExtractionProvider, MockOCRProvider, OCRProvider, RuleBasedInsuranceExtractionProvider


class PacketNotFoundError(LookupError):
    pass


class WorkflowConflictError(RuntimeError):
    pass


class ClaimPacketWorkflowService:
    """In-memory insurance claims packet workflow service."""

    def __init__(
        self,
        ocr_provider: OCRProvider | None = None,
        extraction_provider: ExtractionProvider | None = None,
    ) -> None:
        self._packets: dict[UUID, ClaimPacketRecord] = {}
        self._audit_events: list[AuditEvent] = []
        self._ocr_provider = ocr_provider or MockOCRProvider()
        self._extraction_provider = extraction_provider or RuleBasedInsuranceExtractionProvider()

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
            ocr = self._parse_document(document)
            document.document_type = self._extraction_provider.classify_document(document, ocr)
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
            ocr = self._parse_document(document)
            document.extracted_fields = self._extraction_provider.extract_fields(document, ocr)

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
        if not packet.checklist:
            raise WorkflowConflictError("Checklist must be evaluated before review.")

        if review.decision == ReviewDecision.APPROVE:
            for task in packet.review_tasks:
                if task.status == ReviewTaskStatus.OPEN:
                    task.status = ReviewTaskStatus.RESOLVED
                    task.resolved_at = utc_now()
                    task.reviewer = review.reviewer
                    task.notes = review.notes
            packet.status = PacketStatus.APPROVED
        else:
            if not any(task.status == ReviewTaskStatus.OPEN for task in packet.review_tasks):
                packet.review_tasks.append(ReviewTask(reason="Reviewer requested changes"))
            packet.status = PacketStatus.NEEDS_REVIEW
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
        open_review_tasks = sum(task.status == ReviewTaskStatus.OPEN for task in packet.review_tasks)
        if packet.status != PacketStatus.APPROVED:
            raise WorkflowConflictError("Claim packet must be approved before export.")
        if open_review_tasks:
            raise WorkflowConflictError("Open review tasks must be resolved before export.")

        fields = {
            f"{document.document_type.value}.{document.id}.{field.name}": field.value
            for document in packet.documents
            for field in document.extracted_fields
        }
        packet.status = PacketStatus.EXPORTED
        packet.touch()
        self._audit(packet.id, AuditAction.PACKET_EXPORTED, detail={"field_count": len(fields)})
        return ExportSummary(
            packet_id=packet.id,
            claim_reference=packet.claim_reference,
            claimant_name=packet.claimant_name,
            loss_type=packet.loss_type,
            status=packet.status,
            document_count=len(packet.documents),
            checklist_passed=sum(item.status == ChecklistStatus.PASS for item in packet.checklist),
            checklist_failed=sum(item.status == ChecklistStatus.FAIL for item in packet.checklist),
            open_review_tasks=open_review_tasks,
            fields=fields,
            documents=[
                {
                    "document_id": document.id,
                    "filename": document.filename,
                    "document_type": document.document_type,
                    "extracted_fields": document.extracted_fields,
                }
                for document in packet.documents
            ],
            checklist=packet.checklist,
        )

    def list_audit_events(self, packet_id: UUID | None = None) -> list[AuditEvent]:
        if packet_id is None:
            return list(self._audit_events)
        return [event for event in self._audit_events if event.packet_id == packet_id]

    def _parse_document(self, document: ClaimDocumentRecord) -> OCRResult:
        ocr = self._ocr_provider.parse_document(document)
        document.ocr_provider = ocr.provider
        document.ocr_text = ocr.text
        return ocr

    def _build_claim_checklist(self, packet: ClaimPacketRecord) -> list[ChecklistItem]:
        present_types = {document.document_type for document in packet.documents}
        required = [
            (DocumentType.CLAIM_FORM, "Claim form present"),
            (DocumentType.IDENTITY_DOCUMENT, "Claimant identity evidence present"),
            (DocumentType.INCIDENT_REPORT, "Incident or loss report present"),
        ]
        loss_type = packet.loss_type.lower()
        if any(token in loss_type for token in ["auto", "property", "vehicle"]):
            required.append((DocumentType.REPAIR_INVOICE, "Repair estimate or invoice present"))
        if any(token in loss_type for token in ["medical", "injury", "health"]):
            required.append((DocumentType.MEDICAL_BILL, "Medical bill or treatment evidence present"))
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
