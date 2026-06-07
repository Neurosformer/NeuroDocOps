from __future__ import annotations

import re
from typing import Protocol

from packages.domain.neurodocops_domain.models import (
    Citation,
    ClaimDocumentRecord,
    DocumentType,
    ExtractedField,
    OCRPage,
    OCRResult,
)


class OCRProvider(Protocol):
    """Contract for OCR and layout providers such as Azure, Google, AWS, or PaddleOCR."""

    name: str

    def parse_document(self, document: ClaimDocumentRecord) -> OCRResult:
        """Return normalized text and page-level OCR output for a claim document."""


class ExtractionProvider(Protocol):
    """Contract for classification and schema-based extraction providers."""

    name: str

    def classify_document(self, document: ClaimDocumentRecord, ocr: OCRResult) -> DocumentType:
        """Classify one document using OCR/layout output."""

    def extract_fields(self, document: ClaimDocumentRecord, ocr: OCRResult) -> list[ExtractedField]:
        """Extract structured fields with confidence and citations."""


class MockOCRProvider:
    """Deterministic OCR adapter for local development and tests.

    The MVP accepts text directly in API payloads. This adapter preserves the
    same contract a real OCR provider will implement later.
    """

    name = "mock-ocr"

    def parse_document(self, document: ClaimDocumentRecord) -> OCRResult:
        return OCRResult(
            provider=self.name,
            text=" ".join(document.text.split()),
            pages=[OCRPage(page=1, text=document.text)],
            metadata={"source": "payload_text"},
        )


class RuleBasedInsuranceExtractionProvider:
    """Deterministic insurance extraction adapter for the first product loop."""

    name = "rule-based-insurance-v0"

    def classify_document(self, document: ClaimDocumentRecord, ocr: OCRResult) -> DocumentType:
        lowered = ocr.text.lower()
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

    def extract_fields(self, document: ClaimDocumentRecord, ocr: OCRResult) -> list[ExtractedField]:
        snippet = ocr.text[:180] or document.filename
        common = [
            ExtractedField(
                name="source_filename",
                value=document.filename,
                confidence=0.99,
                citation=Citation(document_id=document.id, page=1, snippet=document.filename),
            ),
            ExtractedField(
                name="ocr_provider",
                value=ocr.provider,
                confidence=1.0,
                citation=Citation(document_id=document.id, page=1, snippet=ocr.provider),
            ),
        ]
        fields = common + self._extract_structured_fields(document, ocr)
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
        return fields + [
            ExtractedField(
                name=field_name_by_type[document.document_type],
                value=snippet,
                confidence=confidence,
                citation=Citation(document_id=document.id, page=1, snippet=snippet),
            )
        ]

    def _extract_structured_fields(self, document: ClaimDocumentRecord, ocr: OCRResult) -> list[ExtractedField]:
        patterns_by_type = {
            DocumentType.CLAIM_FORM: {
                "claim_number": r"claim\s+number\s+([A-Z0-9-]+)",
                "policy_number": r"policy\s+number\s+([A-Z0-9-]+)",
                "loss_date": r"loss\s+date\s+(\d{4}-\d{2}-\d{2})",
            },
            DocumentType.INCIDENT_REPORT: {
                "loss_date": r"loss\s+date\s+(\d{4}-\d{2}-\d{2})",
                "incident_date": r"incident\s+date\s+(\d{4}-\d{2}-\d{2})",
            },
            DocumentType.REPAIR_INVOICE: {
                "invoice_amount": r"(?:amount\s+due|grand\s+total|total)\s+([0-9]+(?:\.[0-9]{2})?\s*(?:USD|EUR|GBP)?)",
            },
            DocumentType.MEDICAL_BILL: {
                "provider_name": r"(?:provider|clinic|hospital)\s+([A-Z][A-Za-z0-9 &.-]+)",
                "service_date": r"service\s+date\s+(\d{4}-\d{2}-\d{2})",
                "total_amount": r"(?:total|amount\s+due)\s+([0-9]+(?:\.[0-9]{2})?\s*(?:USD|EUR|GBP)?)",
            },
            DocumentType.IDENTITY_DOCUMENT: {
                "identity_name": r"(?:claimant|for)\s+([A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)",
            },
            DocumentType.POLICY_DOCUMENT: {
                "policy_number": r"policy\s+number\s+([A-Z0-9-]+)",
            },
        }
        fields: list[ExtractedField] = []
        for name, pattern in patterns_by_type.get(document.document_type, {}).items():
            match = re.search(pattern, ocr.text, flags=re.IGNORECASE)
            if match:
                fields.append(
                    ExtractedField(
                        name=name,
                        value=match.group(1).strip(" .,"),
                        confidence=0.94,
                        citation=Citation(document_id=document.id, page=1, snippet=match.group(0).strip()),
                    )
                )
        return fields
