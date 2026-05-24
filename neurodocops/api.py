from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException, status

from neurodocops.models import AuditEvent, ClaimPacketCreate, ClaimPacketRecord, ExportSummary, ReviewRequest
from neurodocops.service import ClaimPacketWorkflowService, PacketNotFoundError


service = ClaimPacketWorkflowService()
app = FastAPI(
    title="NeuroDocOps API",
    version="0.2.0",
    description="Insurance claims packet workflow API for document intake, checklist review, approval, export, and audit events.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/claim-packets", response_model=ClaimPacketRecord, status_code=status.HTTP_201_CREATED)
def intake_claim_packet(payload: ClaimPacketCreate) -> ClaimPacketRecord:
    return service.intake_packet(payload)


@app.get("/claim-packets", response_model=list[ClaimPacketRecord])
def list_claim_packets() -> list[ClaimPacketRecord]:
    return service.list_packets()


@app.get("/claim-packets/{packet_id}", response_model=ClaimPacketRecord)
def get_claim_packet(packet_id: UUID) -> ClaimPacketRecord:
    return _get_or_404(packet_id)


@app.post("/claim-packets/{packet_id}/classify", response_model=ClaimPacketRecord)
def classify_claim_packet(packet_id: UUID) -> ClaimPacketRecord:
    try:
        return service.classify_documents(packet_id)
    except PacketNotFoundError as exc:
        raise _not_found(packet_id) from exc


@app.post("/claim-packets/{packet_id}/extract", response_model=ClaimPacketRecord)
def extract_claim_packet(packet_id: UUID) -> ClaimPacketRecord:
    try:
        return service.extract_packet(packet_id)
    except PacketNotFoundError as exc:
        raise _not_found(packet_id) from exc


@app.post("/claim-packets/{packet_id}/checklist", response_model=ClaimPacketRecord)
def evaluate_claim_packet_checklist(packet_id: UUID) -> ClaimPacketRecord:
    try:
        return service.evaluate_checklist(packet_id)
    except PacketNotFoundError as exc:
        raise _not_found(packet_id) from exc


@app.post("/claim-packets/{packet_id}/review", response_model=ClaimPacketRecord)
def complete_claim_packet_review(packet_id: UUID, review: ReviewRequest) -> ClaimPacketRecord:
    try:
        return service.complete_review(packet_id, review)
    except PacketNotFoundError as exc:
        raise _not_found(packet_id) from exc


@app.post("/claim-packets/{packet_id}/export", response_model=ExportSummary)
def export_claim_packet(packet_id: UUID) -> ExportSummary:
    try:
        return service.export_packet(packet_id)
    except PacketNotFoundError as exc:
        raise _not_found(packet_id) from exc


@app.get("/claim-packets/{packet_id}/audit", response_model=list[AuditEvent])
def list_claim_packet_audit_events(packet_id: UUID) -> list[AuditEvent]:
    _get_or_404(packet_id)
    return service.list_audit_events(packet_id)


def _get_or_404(packet_id: UUID) -> ClaimPacketRecord:
    try:
        return service.get_packet(packet_id)
    except PacketNotFoundError as exc:
        raise _not_found(packet_id) from exc


def _not_found(packet_id: UUID) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim packet not found: {packet_id}")
