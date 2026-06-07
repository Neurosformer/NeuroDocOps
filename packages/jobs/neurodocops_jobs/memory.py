from __future__ import annotations

from collections import deque
from uuid import UUID

from .models import JobEnvelope, JobStatus, JobStatusRecord


class InMemoryJobQueue:
    """Deterministic job queue for local tests and one-process development."""

    def __init__(self) -> None:
        self._jobs: deque[JobEnvelope] = deque()
        self._statuses: dict[UUID, JobStatusRecord] = {}

    def enqueue(self, job: JobEnvelope) -> JobStatusRecord:
        status = JobStatusRecord.queued(job)
        self._jobs.append(job)
        self._statuses[job.id] = status
        return status

    def dequeue(self, timeout_seconds: int = 5) -> JobEnvelope | None:
        if not self._jobs:
            return None
        return self._jobs.popleft()

    def get_status(self, job_id: UUID) -> JobStatusRecord | None:
        return self._statuses.get(job_id)

    def set_status(self, job_id: UUID, status: JobStatus, error: str | None = None) -> JobStatusRecord:
        current = self._statuses[job_id]
        updated = current.with_status(status, error=error)
        self._statuses[job_id] = updated
        return updated

    def health_check(self) -> bool:
        return True
