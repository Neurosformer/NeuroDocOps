from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PacketStatus(str, Enum):
    INTAKED = "intaked"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    EXPORTED = "exported"


class DocumentType(str, Enum):
    CLAIM_FORM = "claim_form"
    MEDICAL_BILL = "medical_bill"
    REPAIR_INVOICE = "repair_invoice"
    IDENTITY_DOCUMENT = "identity_document"
    INCIDENT_REPORT = "incident_report"
    POLICY_DOCUMENT = "policy_document"
    UNKNOWN = "unknown"


class ReviewTaskStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"


class ChecklistStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


class Citation(BaseModel):
    document_id: UUID
    page: int = Field(default=1, ge=1)
    snippet: str = Field(min_length=1)


class ExtractedField(BaseModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    citation: Citation


class ClaimDocumentCreate(BaseModel):
    filename: str = Field(min_length=1)
    text: str = Field(min_length=1, description="OCR or extracted text for the MVP workflow")
    content_type: str = Field(default="application/pdf", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimPacketCreate(BaseModel):
    claim_reference: str = Field(min_length=1)
    claimant_name: str = Field(min_length=1)
    loss_type: str = Field(default="unknown", min_length=1)
    documents: list[ClaimDocumentCreate] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimDocumentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    text: str
    content_type: str = "application/pdf"
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_type: DocumentType = DocumentType.UNKNOWN
    extracted_fields: list[ExtractedField] = Field(default_factory=list)


class ChecklistItem(BaseModel):
    name: str = Field(min_length=1)
    status: ChecklistStatus
    detail: str
    required_document_type: DocumentType | None = None


class ReviewTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID | None = None
    reason: str = Field(min_length=1)
    status: ReviewTaskStatus = ReviewTaskStatus.OPEN
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None
    reviewer: str | None = None
    notes: str | None = None


class ClaimPacketRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    claim_reference: str
    claimant_name: str
    loss_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: PacketStatus = PacketStatus.INTAKED
    documents: list[ClaimDocumentRecord]
    checklist: list[ChecklistItem] = Field(default_factory=list)
    review_tasks: list[ReviewTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()


class ReviewRequest(BaseModel):
    decision: ReviewDecision
    reviewer: str = Field(min_length=1)
    notes: str | None = None


class ExportSummary(BaseModel):
    packet_id: UUID
    claim_reference: str
    status: PacketStatus
    document_count: int
    checklist_passed: int
    checklist_failed: int
    open_review_tasks: int
    fields: dict[str, str]


class AuditAction(str, Enum):
    PACKET_INTAKED = "packet_intaked"
    DOCUMENTS_CLASSIFIED = "documents_classified"
    FIELDS_EXTRACTED = "fields_extracted"
    CHECKLIST_EVALUATED = "checklist_evaluated"
    REVIEW_COMPLETED = "review_completed"
    PACKET_EXPORTED = "packet_exported"


class AuditEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    packet_id: UUID
    action: AuditAction
    actor: str = "system"
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
