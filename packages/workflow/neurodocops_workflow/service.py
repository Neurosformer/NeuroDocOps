from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from packages.domain.neurodocops_domain.models import (
    AuditAction,
    AuditEvent,
    ChecklistItem,
    ChecklistStatus,
    ClaimDocumentCreate,
    ClaimDocumentRecord,
    ClaimPacketCreate,
    ClaimPacketRecord,
    DocumentType,
    ExportSummary,
    FieldCorrectionRequest,
    OCRResult,
    PacketStatus,
    ReviewDecision,
    ReviewRequest,
    ReviewTaskPriority,
    ReviewTaskQueueItem,
    ReviewTask,
    ReviewTaskStatus,
    utc_now,
)
from packages.providers.neurodocops_providers import (
    ExtractionProvider,
    OCRProvider,
    ProviderRegistry,
    create_provider_registry,
)
from packages.storage.neurodocops_storage import InMemoryPacketRepository, PacketRepository


class PacketNotFoundError(LookupError):
    pass


class WorkflowConflictError(RuntimeError):
    pass


class ReviewTaskNotFoundError(LookupError):
    pass


class ClaimPacketWorkflowService:
    """Insurance claims packet workflow service.

    This is the domain workflow implementation used by the API and future
    worker service. Persistence and async execution should plug in below this
    boundary instead of living inside the FastAPI route handlers.
    """

    def __init__(
        self,
        ocr_provider: OCRProvider | None = None,
        extraction_provider: ExtractionProvider | None = None,
        repository: PacketRepository | None = None,
        provider_registry: ProviderRegistry | None = None,
        source_bytes_loader: Callable[[ClaimDocumentRecord], bytes | None] | None = None,
    ) -> None:
        self._source_bytes_loader = source_bytes_loader
        self._provider_registry = provider_registry
        if self._provider_registry is not None and source_bytes_loader is not None:
            self._provider_registry._source_bytes_loader = source_bytes_loader
        if ocr_provider is None or extraction_provider is None:
            self._provider_registry = self._provider_registry or create_provider_registry(source_bytes_loader=source_bytes_loader)
        self._ocr_provider = ocr_provider or self._provider_registry.create_ocr_provider()
        self._extraction_provider = extraction_provider or self._provider_registry.create_extraction_provider()
        self._repository = repository or InMemoryPacketRepository()

    def intake_packet(self, payload: ClaimPacketCreate) -> ClaimPacketRecord:
        packet = ClaimPacketRecord(
            claim_reference=payload.claim_reference,
            claimant_name=payload.claimant_name,
            loss_type=payload.loss_type,
            metadata=payload.metadata,
            documents=[ClaimDocumentRecord(**document.model_dump()) for document in payload.documents],
        )
        self._repository.add_packet(packet)
        self._audit(packet.id, AuditAction.PACKET_INTAKED, detail={"claim_reference": packet.claim_reference})
        return packet

    def list_packets(self) -> list[ClaimPacketRecord]:
        return self._repository.list_packets()

    def list_review_queue(
        self,
        *,
        assignee: str | None = None,
        status: ReviewTaskStatus | None = ReviewTaskStatus.OPEN,
        priority: ReviewTaskPriority | None = None,
        due_before: datetime | None = None,
        unassigned: bool = False,
    ) -> list[ReviewTaskQueueItem]:
        items: list[ReviewTaskQueueItem] = []
        for packet in self._repository.list_packets():
            for task in packet.review_tasks:
                if status is not None and task.status != status:
                    continue
                if assignee is not None and task.assignee != assignee:
                    continue
                if unassigned and task.assignee is not None:
                    continue
                if priority is not None and task.priority != priority:
                    continue
                if due_before is not None and (task.due_at is None or task.due_at > due_before):
                    continue
                items.append(
                    ReviewTaskQueueItem(
                        packet_id=packet.id,
                        claim_reference=packet.claim_reference,
                        claimant_name=packet.claimant_name,
                        loss_type=packet.loss_type,
                        packet_status=packet.status,
                        task=task,
                    )
                )

        priority_rank = {
            ReviewTaskPriority.URGENT: 0,
            ReviewTaskPriority.HIGH: 1,
            ReviewTaskPriority.NORMAL: 2,
            ReviewTaskPriority.LOW: 3,
        }
        max_datetime = datetime.max.replace(tzinfo=timezone.utc)
        items.sort(key=lambda item: (item.task.due_at is None, item.task.due_at or max_datetime, priority_rank[item.task.priority], item.task.created_at))
        return items

    def add_document_to_packet(self, packet_id: UUID, document: ClaimDocumentCreate) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        record = ClaimDocumentRecord(**document.model_dump())
        packet.documents.append(record)
        packet.touch()
        self._repository.save_packet(packet)
        self._audit(
            packet.id,
            AuditAction.DOCUMENT_UPLOADED,
            detail={
                "document_id": str(record.id),
                "filename": record.filename,
                "content_type": record.content_type,
                "source_object_key": record.source_object.key if record.source_object else None,
            },
        )
        return packet

    def get_packet(self, packet_id: UUID) -> ClaimPacketRecord:
        packet = self._repository.get_packet(packet_id)
        if packet is None:
            raise PacketNotFoundError(str(packet_id))
        return packet

    def classify_documents(self, packet_id: UUID) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        for document in packet.documents:
            ocr = self._parse_document(document)
            document.document_type = self._extraction_provider.classify_document(document, ocr)
        packet.status = PacketStatus.CLASSIFIED
        packet.touch()
        self._repository.save_packet(packet)
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
        self._repository.save_packet(packet)
        self._audit(packet.id, AuditAction.FIELDS_EXTRACTED, detail={"field_count": self._field_count(packet)})
        return packet

    def evaluate_checklist(self, packet_id: UUID) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        if packet.status in {PacketStatus.INTAKED, PacketStatus.CLASSIFIED}:
            self.extract_packet(packet_id)

        packet.checklist = self._build_claim_checklist(packet)
        packet.review_tasks = self._build_review_tasks(packet)
        packet.status = PacketStatus.NEEDS_REVIEW
        packet.touch()
        self._repository.save_packet(packet)
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
            if any(task.status == ReviewTaskStatus.OPEN for task in packet.review_tasks):
                raise WorkflowConflictError("Open review tasks must be resolved before approval.")
            packet.status = PacketStatus.APPROVED
        else:
            if not any(task.status == ReviewTaskStatus.OPEN for task in packet.review_tasks):
                packet.review_tasks.append(ReviewTask(reason="Reviewer requested changes"))
            packet.status = PacketStatus.NEEDS_REVIEW
        packet.touch()
        self._repository.save_packet(packet)
        self._audit(
            packet.id,
            AuditAction.REVIEW_COMPLETED,
            actor=review.reviewer,
            detail={"decision": review.decision.value, "notes": review.notes},
        )
        return packet

    def resolve_review_task(self, packet_id: UUID, task_id: UUID, reviewer: str, notes: str | None = None) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        task = self._get_review_task(packet, task_id)
        previous_status = task.status
        task.status = ReviewTaskStatus.RESOLVED
        task.resolved_at = utc_now()
        task.reviewer = reviewer
        task.notes = notes
        if packet.status == PacketStatus.EXPORTED:
            packet.status = PacketStatus.APPROVED
        packet.touch()
        self._repository.save_packet(packet)
        self._audit(
            packet.id,
            AuditAction.REVIEW_TASK_RESOLVED,
            actor=reviewer,
            detail={
                "task_id": str(task.id),
                "document_id": str(task.document_id) if task.document_id else None,
                "reason": task.reason,
                "previous_status": previous_status.value,
                "status": task.status.value,
                "notes": notes,
            },
        )
        return packet

    def reopen_review_task(self, packet_id: UUID, task_id: UUID, reviewer: str, notes: str | None = None) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        task = self._get_review_task(packet, task_id)
        previous_status = task.status
        task.status = ReviewTaskStatus.OPEN
        task.resolved_at = None
        task.reviewer = reviewer
        task.notes = notes
        if packet.status in {PacketStatus.APPROVED, PacketStatus.EXPORTED}:
            packet.status = PacketStatus.NEEDS_REVIEW
        packet.touch()
        self._repository.save_packet(packet)
        self._audit(
            packet.id,
            AuditAction.REVIEW_TASK_REOPENED,
            actor=reviewer,
            detail={
                "task_id": str(task.id),
                "document_id": str(task.document_id) if task.document_id else None,
                "reason": task.reason,
                "previous_status": previous_status.value,
                "status": task.status.value,
                "notes": notes,
            },
        )
        return packet

    def update_review_task(self, packet_id: UUID, task_id: UUID, actor: str, updates: dict[str, object]) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        task = self._get_review_task(packet, task_id)
        previous_assignee = task.assignee
        previous_priority = task.priority
        previous_due_at = task.due_at
        previous_notes = task.notes

        if "assignee" in updates:
            task.assignee = updates["assignee"]
        if "priority" in updates and updates["priority"] is not None:
            task.priority = updates["priority"]
        if "due_at" in updates:
            task.due_at = updates["due_at"]
        if "notes" in updates:
            task.notes = updates["notes"]

        packet.touch()
        self._repository.save_packet(packet)

        detail = {
            "task_id": str(task.id),
            "document_id": str(task.document_id) if task.document_id else None,
            "reason": task.reason,
            "previous_assignee": previous_assignee,
            "assignee": task.assignee,
            "previous_priority": previous_priority.value,
            "priority": task.priority.value,
            "previous_due_at": previous_due_at.isoformat() if previous_due_at else None,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "previous_notes": previous_notes,
            "notes": task.notes,
        }
        if previous_assignee != task.assignee:
            self._audit(packet.id, AuditAction.REVIEW_TASK_ASSIGNED, actor=actor, detail=detail)
        if previous_priority != task.priority or previous_due_at != task.due_at or previous_notes != task.notes:
            self._audit(packet.id, AuditAction.REVIEW_TASK_UPDATED, actor=actor, detail=detail)
        return packet

    def correct_extracted_field(self, packet_id: UUID, document_id: UUID, field_name: str, correction: FieldCorrectionRequest) -> ClaimPacketRecord:
        packet = self.get_packet(packet_id)
        document = next((candidate for candidate in packet.documents if candidate.id == document_id), None)
        if document is None:
            raise WorkflowConflictError(f"Document not found in packet: {document_id}")
        field = next((candidate for candidate in document.extracted_fields if candidate.name == field_name), None)
        if field is None:
            raise WorkflowConflictError(f"Extracted field not found: {field_name}")

        previous_value = field.value
        field.value = correction.value
        field.confidence = 1.0
        packet.touch()
        self._repository.save_packet(packet)
        self._audit(
            packet.id,
            AuditAction.FIELD_CORRECTED,
            actor=correction.reviewer,
            detail={
                "document_id": str(document.id),
                "filename": document.filename,
                "field_name": field.name,
                "previous_value": previous_value,
                "corrected_value": field.value,
                "notes": correction.notes,
            },
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
        self._repository.save_packet(packet)
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
        return self._repository.list_audit_events(packet_id)

    def active_provider_payload(self) -> list[dict[str, object]]:
        if self._provider_registry is not None:
            return self._provider_registry.active_provider_payload()
        return [
            {
                "kind": "ocr",
                "name": getattr(self._ocr_provider, "name", self._ocr_provider.__class__.__name__),
                "tier": "free",
                "paid": False,
                "live_enabled": False,
                "implemented": True,
                "adapter": self._ocr_provider.__class__.__name__,
            },
            {
                "kind": "extraction",
                "name": getattr(self._extraction_provider, "name", self._extraction_provider.__class__.__name__),
                "tier": "free",
                "paid": False,
                "live_enabled": False,
                "implemented": True,
                "adapter": self._extraction_provider.__class__.__name__,
            },
        ]

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

    def _get_review_task(self, packet: ClaimPacketRecord, task_id: UUID) -> ReviewTask:
        task = next((candidate for candidate in packet.review_tasks if candidate.id == task_id), None)
        if task is None:
            raise ReviewTaskNotFoundError(str(task_id))
        return task

    def _audit(
        self,
        packet_id: UUID,
        action: AuditAction,
        actor: str = "system",
        detail: dict[str, object] | None = None,
    ) -> None:
        self._repository.add_audit_event(AuditEvent(packet_id=packet_id, action=action, actor=actor, detail=detail or {}))
