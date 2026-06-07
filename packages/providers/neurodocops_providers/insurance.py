from __future__ import annotations

import re
import zlib
from collections.abc import Callable
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


class LocalPDFTextOCRProvider:
    """Free local parser for embedded text in digital PDFs.

    This is not scanned-image OCR. It reads text operators from uploaded PDF
    bytes when available and falls back to request payload text when parsing is
    unsupported, empty, or unavailable.
    """

    name = "local-pdf-text"

    def __init__(self, source_bytes_loader: Callable[[ClaimDocumentRecord], bytes | None] | None = None) -> None:
        self._source_bytes_loader = source_bytes_loader

    def parse_document(self, document: ClaimDocumentRecord) -> OCRResult:
        data = self._source_bytes_loader(document) if self._source_bytes_loader is not None else None
        if not data:
            return self._fallback_to_payload_text(document, "source_bytes_unavailable")
        if document.content_type != "application/pdf" and not document.filename.lower().endswith(".pdf"):
            return self._fallback_to_payload_text(document, "not_pdf")

        extracted_text = _extract_pdf_text(data)
        if not extracted_text:
            return self._fallback_to_payload_text(document, "no_embedded_text")

        return OCRResult(
            provider=self.name,
            text=extracted_text,
            pages=[OCRPage(page=1, text=extracted_text)],
            metadata={
                "source": "uploaded_pdf_bytes",
                "mode": "embedded_pdf_text",
                "parser": "local_pdf_text",
            },
        )

    def _fallback_to_payload_text(self, document: ClaimDocumentRecord, reason: str) -> OCRResult:
        fallback = " ".join(document.text.split()) or f"Unparsed source document: {document.filename}"
        return OCRResult(
            provider=self.name,
            text=fallback,
            pages=[OCRPage(page=1, text=fallback)],
            metadata={"source": "payload_text", "mode": "embedded_pdf_text", "fallback_reason": reason},
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


def _extract_pdf_text(data: bytes) -> str:
    parts: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, flags=re.DOTALL):
        stream = match.group(1).strip(b"\r\n")
        header = data[max(0, match.start() - 240) : match.start()]
        if b"/FlateDecode" in header:
            try:
                stream = zlib.decompress(stream)
            except zlib.error:
                continue
        parts.extend(_extract_pdf_text_operators(stream))
    return " ".join(" ".join(parts).split())


def _extract_pdf_text_operators(stream: bytes) -> list[str]:
    try:
        text = stream.decode("latin-1")
    except UnicodeDecodeError:
        return []
    values: list[str] = []
    for match in re.finditer(r"\((?:\\.|[^\\)])*\)\s*Tj", text):
        values.append(_decode_pdf_literal(match.group(0).rsplit(")", 1)[0][1:]))
    for array in re.finditer(r"\[(.*?)\]\s*TJ", text, flags=re.DOTALL):
        chunks = [_decode_pdf_literal(item.group(1)) for item in re.finditer(r"\((?:\\.|[^\\)])*\)", array.group(1))]
        if chunks:
            values.append("".join(chunks))
    return [value for value in values if value.strip()]


def _decode_pdf_literal(value: str) -> str:
    replacements = {
        r"\(": "(",
        r"\)": ")",
        r"\\": "\\",
        r"\n": "\n",
        r"\r": "\r",
        r"\t": "\t",
        r"\b": "\b",
        r"\f": "\f",
    }
    for raw, decoded in replacements.items():
        value = value.replace(raw, decoded)
    return re.sub(r"\\([0-7]{1,3})", lambda match: chr(int(match.group(1), 8)), value)
