from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException, status

from neurodocops.models import AuditEvent, DocumentCreate, DocumentRecord, ReviewRequest
from neurodocops.service import DocumentNotFoundError, DocumentWorkflowService


service = DocumentWorkflowService()
app = FastAPI(
    title="NeuroDocOps API",
    version="0.1.0",
    description="MVP API for regulated document ingestion, extraction review, and audit events.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
def ingest_document(payload: DocumentCreate) -> DocumentRecord:
    return service.ingest_document(payload)


@app.get("/documents", response_model=list[DocumentRecord])
def list_documents() -> list[DocumentRecord]:
    return service.list_documents()


@app.get("/documents/{document_id}", response_model=DocumentRecord)
def get_document(document_id: UUID) -> DocumentRecord:
    return _get_or_404(document_id)


@app.post("/documents/{document_id}/classify", response_model=DocumentRecord)
def classify_document(document_id: UUID) -> DocumentRecord:
    try:
        return service.classify_document(document_id)
    except DocumentNotFoundError as exc:
        raise _not_found(document_id) from exc


@app.post("/documents/{document_id}/extract", response_model=DocumentRecord)
def extract_fields(document_id: UUID) -> DocumentRecord:
    try:
        return service.extract_fields(document_id)
    except DocumentNotFoundError as exc:
        raise _not_found(document_id) from exc


@app.post("/documents/{document_id}/review", response_model=DocumentRecord)
def complete_review(document_id: UUID, review: ReviewRequest) -> DocumentRecord:
    try:
        return service.complete_review(document_id, review)
    except DocumentNotFoundError as exc:
        raise _not_found(document_id) from exc


@app.get("/documents/{document_id}/audit", response_model=list[AuditEvent])
def list_document_audit_events(document_id: UUID) -> list[AuditEvent]:
    _get_or_404(document_id)
    return service.list_audit_events(document_id)


def _get_or_404(document_id: UUID) -> DocumentRecord:
    try:
        return service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise _not_found(document_id) from exc


def _not_found(document_id: UUID) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document not found: {document_id}")
