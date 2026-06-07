from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from packages.domain.neurodocops_domain.models import utc_now


class JobType(str, Enum):
    PROCESS_PACKET = "process_packet"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PacketProcessRequest(BaseModel):
    steps: list[str] = Field(default_factory=lambda: ["classify", "extract", "checklist"])


class JobEnvelope(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: JobType
    packet_id: UUID
    steps: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())


class JobStatusRecord(BaseModel):
    id: UUID
    type: JobType
    packet_id: UUID
    status: JobStatus
    steps: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str
    updated_at: str = Field(default_factory=lambda: utc_now().isoformat())

    @classmethod
    def queued(cls, job: JobEnvelope) -> "JobStatusRecord":
        return cls(
            id=job.id,
            type=job.type,
            packet_id=job.packet_id,
            status=JobStatus.QUEUED,
            steps=job.steps,
            created_at=job.created_at,
        )

    def with_status(self, status: JobStatus, error: str | None = None) -> "JobStatusRecord":
        return self.model_copy(update={"status": status, "error": error, "updated_at": utc_now().isoformat()})
