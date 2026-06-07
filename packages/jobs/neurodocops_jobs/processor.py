from __future__ import annotations

from packages.workflow.neurodocops_workflow import ClaimPacketWorkflowService

from .models import JobEnvelope, JobStatus, JobType
from .queue import JobQueue


class JobProcessor:
    """Executes queued jobs through the same workflow service used by the API."""

    def __init__(self, workflow_service: ClaimPacketWorkflowService) -> None:
        self._workflow_service = workflow_service

    def process(self, job: JobEnvelope, queue: JobQueue) -> None:
        queue.set_status(job.id, JobStatus.RUNNING)
        try:
            if job.type == JobType.PROCESS_PACKET:
                self._process_packet(job)
            else:  # pragma: no cover - enum currently has one value, kept for future safety
                raise ValueError(f"Unsupported job type: {job.type}")
        except Exception as exc:
            queue.set_status(job.id, JobStatus.FAILED, error=str(exc))
            raise
        queue.set_status(job.id, JobStatus.SUCCEEDED)

    def _process_packet(self, job: JobEnvelope) -> None:
        steps = job.steps or ["classify", "extract", "checklist"]
        for step in steps:
            if step == "classify":
                self._workflow_service.classify_documents(job.packet_id)
            elif step == "extract":
                self._workflow_service.extract_packet(job.packet_id)
            elif step == "checklist":
                self._workflow_service.evaluate_checklist(job.packet_id)
            else:
                raise ValueError(f"Unsupported packet processing step: {step}")


def process_next_job(queue: JobQueue, processor: JobProcessor, timeout_seconds: int = 5) -> bool:
    job = queue.dequeue(timeout_seconds=timeout_seconds)
    if job is None:
        return False
    processor.process(job, queue)
    return True
