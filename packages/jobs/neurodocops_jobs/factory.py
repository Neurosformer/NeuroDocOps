from __future__ import annotations

import os

from .memory import InMemoryJobQueue
from .queue import JobQueue


def create_job_queue() -> JobQueue:
    """Create the configured job queue for API and worker runtime."""

    backend = os.getenv("NEURODOCOPS_JOB_QUEUE_BACKEND", "memory").strip().lower()
    if backend in {"memory", "inmemory", "in-memory"}:
        return InMemoryJobQueue()
    if backend == "redis":
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL must be set when NEURODOCOPS_JOB_QUEUE_BACKEND=redis")
        from .redis_queue import RedisJobQueue

        return RedisJobQueue(redis_url)
    raise RuntimeError(f"Unsupported NEURODOCOPS_JOB_QUEUE_BACKEND: {backend}")
