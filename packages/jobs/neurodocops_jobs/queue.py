from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .models import JobEnvelope, JobStatus, JobStatusRecord


class JobQueue(Protocol):
    def enqueue(self, job: JobEnvelope) -> JobStatusRecord:
        """Add a job to the queue and return its initial status."""

    def dequeue(self, timeout_seconds: int = 5) -> JobEnvelope | None:
        """Return the next job or None when no job is available before timeout."""

    def get_status(self, job_id: UUID) -> JobStatusRecord | None:
        """Return the current job status if it exists."""

    def set_status(self, job_id: UUID, status: JobStatus, error: str | None = None) -> JobStatusRecord:
        """Persist a status transition for a known job."""

    def health_check(self) -> bool:
        """Return True when the queue dependency is reachable."""
