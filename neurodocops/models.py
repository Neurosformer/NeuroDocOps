from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentStatus(str, Enum):
    INGESTED = "ingested"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"


class DocumentType(str, Enum):
    CLAIM_FORM = "claim_form"
    INVOICE = "invoice"
    CONTRACT = "contract"
    IDENTITY_DOCUMENT = "identity_document"
    COMPLIANCE_REPORT = "compliance_report"
    UNKNOWN = "unknown"


class ConfidenceBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Citation(BaseModel):
    page: int = Field(ge=1)
    snippet: str = Field(min_length=1)


class ExtractedField(BaseModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    citation: Citation

    @property
    def confidence_band(self) -> ConfidenceBand:
        if self.confidence >= 0.85:
            return ConfidenceBand.HIGH
        if self.confidence >= 0.6:
            return ConfidenceBand.MEDIUM
        return ConfidenceBand.LOW


class DocumentCreate(BaseModel):
    filename: str = Field(min_length=1)
    content_type: str = Field(default="application/pdf", min_length=1)
    text: str = Field(min_length=1, description="OCR or extracted text for the MVP workflow")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    content_type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: DocumentStatus = DocumentStatus.INGESTED
    document_type: DocumentType = DocumentType.UNKNOWN
    extracted_fields: list[ExtractedField] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"


class ReviewRequest(BaseModel):
    decision: ReviewDecision
    reviewer: str = Field(min_length=1)
    notes: str | None = None


class AuditAction(str, Enum):
    DOCUMENT_INGESTED = "document_ingested"
    DOCUMENT_CLASSIFIED = "document_classified"
    FIELDS_EXTRACTED = "fields_extracted"
    REVIEW_COMPLETED = "review_completed"


class AuditEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    action: AuditAction
    actor: str = "system"
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
