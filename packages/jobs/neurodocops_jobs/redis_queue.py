from __future__ import annotations

import json
from uuid import UUID

from redis import Redis

from .models import JobEnvelope, JobStatus, JobStatusRecord


class RedisJobQueue:
    """Redis-backed packet processing queue using a list plus per-job status keys."""

    def __init__(self, redis_url: str, queue_name: str = "neurodocops:jobs") -> None:
        if not redis_url:
            raise RuntimeError("REDIS_URL must be set when NEURODOCOPS_JOB_QUEUE_BACKEND=redis")
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._queue_name = queue_name

    def enqueue(self, job: JobEnvelope) -> JobStatusRecord:
        status = JobStatusRecord.queued(job)
        self._redis.set(self._status_key(job.id), status.model_dump_json())
        self._redis.lpush(self._queue_name, job.model_dump_json())
        return status

    def dequeue(self, timeout_seconds: int = 5) -> JobEnvelope | None:
        item = self._redis.brpop(self._queue_name, timeout=timeout_seconds)
        if item is None:
            return None
        _, payload = item
        return JobEnvelope.model_validate(json.loads(payload))

    def get_status(self, job_id: UUID) -> JobStatusRecord | None:
        payload = self._redis.get(self._status_key(job_id))
        if payload is None:
            return None
        return JobStatusRecord.model_validate(json.loads(payload))

    def set_status(self, job_id: UUID, status: JobStatus, error: str | None = None) -> JobStatusRecord:
        current = self.get_status(job_id)
        if current is None:
            raise KeyError(str(job_id))
        updated = current.with_status(status, error=error)
        self._redis.set(self._status_key(job_id), updated.model_dump_json())
        return updated

    def health_check(self) -> bool:
        self._redis.ping()
        return True

    @staticmethod
    def _status_key(job_id: UUID) -> str:
        return f"neurodocops:jobs:{job_id}"
