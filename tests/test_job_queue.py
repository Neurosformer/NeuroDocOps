import pytest

from neurodocops.models import ClaimDocumentCreate, ClaimPacketCreate, PacketStatus
from neurodocops.service import ClaimPacketWorkflowService
from packages.jobs.neurodocops_jobs import InMemoryJobQueue, JobEnvelope, JobProcessor, JobStatus, JobType, create_job_queue, process_next_job
from packages.storage.neurodocops_storage import InMemoryPacketRepository


def test_in_memory_job_queue_tracks_status_transitions() -> None:
    queue = InMemoryJobQueue()
    packet = _service().intake_packet(_packet_payload())
    job = JobEnvelope(type=JobType.PROCESS_PACKET, packet_id=packet.id, steps=["classify"])

    queued = queue.enqueue(job)
    assert queued.status == JobStatus.QUEUED
    assert queue.get_status(job.id).status == JobStatus.QUEUED

    dequeued = queue.dequeue(timeout_seconds=0)
    assert dequeued == job

    running = queue.set_status(job.id, JobStatus.RUNNING)
    assert running.status == JobStatus.RUNNING


def test_job_processor_runs_packet_workflow_steps() -> None:
    repository = InMemoryPacketRepository()
    queue = InMemoryJobQueue()
    service = _service(repository=repository)
    packet = service.intake_packet(_packet_payload())
    job = JobEnvelope(type=JobType.PROCESS_PACKET, packet_id=packet.id, steps=["classify", "extract", "checklist"])
    queue.enqueue(job)

    assert process_next_job(queue, JobProcessor(service), timeout_seconds=0) is True

    assert queue.get_status(job.id).status == JobStatus.SUCCEEDED
    assert service.get_packet(packet.id).status == PacketStatus.NEEDS_REVIEW
    assert [event.action.value for event in service.list_audit_events(packet.id)] == [
        "packet_intaked",
        "documents_classified",
        "fields_extracted",
        "checklist_evaluated",
    ]


def test_job_processor_marks_failed_jobs() -> None:
    queue = InMemoryJobQueue()
    service = _service()
    packet = service.intake_packet(_packet_payload())
    job = JobEnvelope(type=JobType.PROCESS_PACKET, packet_id=packet.id, steps=["unsupported"])
    queue.enqueue(job)

    with pytest.raises(ValueError, match="Unsupported packet processing step"):
        process_next_job(queue, JobProcessor(service), timeout_seconds=0)

    status = queue.get_status(job.id)
    assert status.status == JobStatus.FAILED
    assert "Unsupported" in status.error


def test_job_queue_factory_defaults_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEURODOCOPS_JOB_QUEUE_BACKEND", raising=False)

    queue = create_job_queue()

    assert isinstance(queue, InMemoryJobQueue)


def test_job_queue_factory_requires_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEURODOCOPS_JOB_QUEUE_BACKEND", "redis")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(RuntimeError, match="REDIS_URL"):
        create_job_queue()


def test_job_queue_factory_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEURODOCOPS_JOB_QUEUE_BACKEND", "sqs")

    with pytest.raises(RuntimeError, match="Unsupported"):
        create_job_queue()


def _service(repository: InMemoryPacketRepository | None = None) -> ClaimPacketWorkflowService:
    return ClaimPacketWorkflowService(repository=repository or InMemoryPacketRepository())


def _packet_payload() -> ClaimPacketCreate:
    return ClaimPacketCreate(
        claim_reference="CLM-JOB-1",
        claimant_name="Taylor Job",
        loss_type="auto",
        documents=[
            ClaimDocumentCreate(filename="claim-form.pdf", text="Claim form with claim number CLM-JOB-1 and policy number P-JOB."),
            ClaimDocumentCreate(filename="incident.pdf", text="Incident report for accident and loss date 2026-05-01."),
            ClaimDocumentCreate(filename="identity.pdf", text="National ID identity document for Taylor Job."),
            ClaimDocumentCreate(filename="invoice.pdf", text="Repair invoice amount due 900 USD."),
        ],
    )
