from __future__ import annotations

import json
import re
from uuid import UUID
from uuid import uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from packages.domain.neurodocops_domain.models import AuditEvent, ClaimDocumentCreate, ClaimPacketCreate, ClaimPacketRecord, ExportSummary, FieldCorrectionRequest, ReviewRequest
from packages.jobs.neurodocops_jobs import JobEnvelope, JobQueue, JobStatusRecord, JobType, PacketProcessRequest, create_job_queue
from packages.providers.neurodocops_providers import ProviderRegistry, create_provider_registry
from packages.security.neurodocops_security import AccessDeniedError, ActorContext, Permission, actor_from_headers, require_permission
from packages.storage.neurodocops_storage import ObjectStore, create_object_store, create_packet_repository
from packages.workflow.neurodocops_workflow import ClaimPacketWorkflowService, PacketNotFoundError, WorkflowConflictError


def create_app(
    service: ClaimPacketWorkflowService | None = None,
    job_queue: JobQueue | None = None,
    object_store: ObjectStore | None = None,
    provider_registry: ProviderRegistry | None = None,
) -> FastAPI:
    registry = provider_registry or (create_provider_registry() if service is None else None)
    workflow_service = service or ClaimPacketWorkflowService(repository=create_packet_repository(), provider_registry=registry)
    queue = job_queue or create_job_queue()
    store = object_store or create_object_store()
    app = FastAPI(
        title="NeuroDocOps API",
        version="0.2.0",
        description="Insurance claims packet workflow API for document intake, checklist review, approval, export, and audit events.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.workflow_service = workflow_service
    app.state.job_queue = queue
    app.state.object_store = store
    app.state.provider_registry = registry

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "api"}

    @app.get("/ready")
    def ready() -> dict[str, object]:
        repository = getattr(workflow_service, "_repository", None)
        health_check = getattr(repository, "health_check", None)
        if health_check is not None:
            try:
                health_check()
            except Exception as exc:  # pragma: no cover - depends on deployed infrastructure failures
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        queue_health_check = getattr(queue, "health_check", None)
        if queue_health_check is not None:
            try:
                queue_health_check()
            except Exception as exc:  # pragma: no cover - depends on deployed infrastructure failures
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        object_store_health_check = getattr(store, "health_check", None)
        if object_store_health_check is not None:
            try:
                object_store_health_check()
            except Exception as exc:  # pragma: no cover - depends on deployed infrastructure failures
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        return {"status": "ready", "service": "api", "providers": workflow_service.active_provider_payload()}

    @app.post("/claim-packets", response_model=ClaimPacketRecord, status_code=status.HTTP_201_CREATED)
    def intake_claim_packet(payload: ClaimPacketCreate, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ClaimPacketRecord:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_CREATE)
        return workflow_service.intake_packet(payload)

    @app.get("/claim-packets", response_model=list[ClaimPacketRecord])
    def list_claim_packets(x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> list[ClaimPacketRecord]:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_READ)
        return workflow_service.list_packets()

    @app.get("/claim-packets/{packet_id}", response_model=ClaimPacketRecord)
    def get_claim_packet(packet_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ClaimPacketRecord:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_READ)
        return _get_or_404(packet_id, workflow_service)

    @app.get("/claim-packets/{packet_id}/documents/{document_id}/source")
    def get_claim_packet_document_source(packet_id: UUID, document_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> Response:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_READ)
        packet = _get_or_404(packet_id, workflow_service)
        document = next((candidate for candidate in packet.documents if candidate.id == document_id), None)
        if document is None or document.source_object is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found.")
        try:
            data = store.get_bytes(document.source_object.key)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document bytes not found.") from exc
        disposition = f'inline; filename="{_safe_filename(document.filename)}"'
        return Response(content=data, media_type=document.source_object.content_type, headers={"Content-Disposition": disposition})

    @app.post("/claim-packets/{packet_id}/documents", response_model=ClaimPacketRecord, status_code=status.HTTP_201_CREATED)
    async def upload_claim_packet_document(
        packet_id: UUID,
        file: UploadFile = File(...),
        text: str = Form(...),
        metadata: str | None = Form(None),
        x_actor: str | None = Header(default=None),
        x_role: str | None = Header(default=None),
    ) -> ClaimPacketRecord:
        _require_headers_permission(x_actor, x_role, Permission.DOCUMENT_UPLOAD)
        _get_or_404(packet_id, workflow_service)
        data = await file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded document is empty.")
        try:
            parsed_metadata = json.loads(metadata) if metadata else {}
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="metadata must be valid JSON.") from exc
        if not isinstance(parsed_metadata, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="metadata must be a JSON object.")

        filename = file.filename or "document.bin"
        content_type = file.content_type or "application/octet-stream"
        key = f"claim-packets/{packet_id}/source-documents/{uuid4()}/{_safe_filename(filename)}"
        source_object = store.put_bytes(key, data, content_type)
        document = ClaimDocumentCreate(
            filename=filename,
            text=text,
            content_type=content_type,
            source_object=source_object,
            metadata=parsed_metadata,
        )
        try:
            return workflow_service.add_document_to_packet(packet_id, document)
        except PacketNotFoundError as exc:  # pragma: no cover - packet is checked before upload
            raise _not_found(packet_id) from exc

    @app.post("/claim-packets/{packet_id}/classify", response_model=ClaimPacketRecord)
    def classify_claim_packet(packet_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ClaimPacketRecord:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_PROCESS)
        try:
            return workflow_service.classify_documents(packet_id)
        except PacketNotFoundError as exc:
            raise _not_found(packet_id) from exc

    @app.post("/claim-packets/{packet_id}/extract", response_model=ClaimPacketRecord)
    def extract_claim_packet(packet_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ClaimPacketRecord:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_PROCESS)
        try:
            return workflow_service.extract_packet(packet_id)
        except PacketNotFoundError as exc:
            raise _not_found(packet_id) from exc

    @app.post("/claim-packets/{packet_id}/checklist", response_model=ClaimPacketRecord)
    def evaluate_claim_packet_checklist(packet_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ClaimPacketRecord:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_PROCESS)
        try:
            return workflow_service.evaluate_checklist(packet_id)
        except PacketNotFoundError as exc:
            raise _not_found(packet_id) from exc

    @app.post("/claim-packets/{packet_id}/process", response_model=JobStatusRecord, status_code=status.HTTP_202_ACCEPTED)
    def enqueue_claim_packet_processing(packet_id: UUID, payload: PacketProcessRequest | None = None, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> JobStatusRecord:
        _require_headers_permission(x_actor, x_role, Permission.PACKET_PROCESS)
        _get_or_404(packet_id, workflow_service)
        request = payload or PacketProcessRequest()
        job = JobEnvelope(type=JobType.PROCESS_PACKET, packet_id=packet_id, steps=request.steps)
        return queue.enqueue(job)

    @app.get("/jobs/{job_id}", response_model=JobStatusRecord)
    def get_job_status(job_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> JobStatusRecord:
        _require_headers_permission(x_actor, x_role, Permission.JOB_READ)
        job_status = queue.get_status(job_id)
        if job_status is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
        return job_status

    @app.post("/claim-packets/{packet_id}/review", response_model=ClaimPacketRecord)
    def complete_claim_packet_review(packet_id: UUID, review: ReviewRequest, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ClaimPacketRecord:
        _require_headers_permission(x_actor, x_role, Permission.REVIEW_COMPLETE)
        try:
            return workflow_service.complete_review(packet_id, review)
        except PacketNotFoundError as exc:
            raise _not_found(packet_id) from exc
        except WorkflowConflictError as exc:
            raise _conflict(str(exc)) from exc

    @app.post("/claim-packets/{packet_id}/documents/{document_id}/fields/{field_name}/correct", response_model=ClaimPacketRecord)
    def correct_claim_packet_field(packet_id: UUID, document_id: UUID, field_name: str, correction: FieldCorrectionRequest, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ClaimPacketRecord:
        actor = _require_headers_permission(x_actor, x_role, Permission.REVIEW_COMPLETE)
        correction = correction.model_copy(update={"reviewer": actor.actor_id})
        try:
            return workflow_service.correct_extracted_field(packet_id, document_id, field_name, correction)
        except PacketNotFoundError as exc:
            raise _not_found(packet_id) from exc
        except WorkflowConflictError as exc:
            raise _conflict(str(exc)) from exc

    @app.post("/claim-packets/{packet_id}/export", response_model=ExportSummary)
    def export_claim_packet(packet_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> ExportSummary:
        _require_headers_permission(x_actor, x_role, Permission.EXPORT_PACKET)
        try:
            return workflow_service.export_packet(packet_id)
        except PacketNotFoundError as exc:
            raise _not_found(packet_id) from exc
        except WorkflowConflictError as exc:
            raise _conflict(str(exc)) from exc

    @app.get("/claim-packets/{packet_id}/audit", response_model=list[AuditEvent])
    def list_claim_packet_audit_events(packet_id: UUID, x_actor: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> list[AuditEvent]:
        _require_headers_permission(x_actor, x_role, Permission.AUDIT_READ)
        _get_or_404(packet_id, workflow_service)
        return workflow_service.list_audit_events(packet_id)

    return app


def _get_or_404(packet_id: UUID, service: ClaimPacketWorkflowService) -> ClaimPacketRecord:
    try:
        return service.get_packet(packet_id)
    except PacketNotFoundError as exc:
        raise _not_found(packet_id) from exc


def _not_found(packet_id: UUID) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim packet not found: {packet_id}")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _require_headers_permission(actor: str | None, role: str | None, permission: Permission) -> ActorContext:
    headers = {}
    if actor is not None:
        headers["x-actor"] = actor
    if role is not None:
        headers["x-role"] = role
    try:
        actor_context = actor_from_headers(headers)
        require_permission(actor_context, permission)
        return actor_context
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def _safe_filename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", filename.strip()).strip(".-")
    return sanitized or "document.bin"


app = create_app()
