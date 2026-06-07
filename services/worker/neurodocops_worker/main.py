from __future__ import annotations

import os

from packages.jobs.neurodocops_jobs import JobProcessor, create_job_queue, process_next_job
from packages.providers.neurodocops_providers import create_provider_registry
from packages.storage.neurodocops_storage import create_packet_repository
from packages.workflow.neurodocops_workflow import ClaimPacketWorkflowService


def main() -> None:
    """Run the worker process and execute queued packet-processing jobs."""

    dequeue_timeout_seconds = int(os.getenv("NEURODOCOPS_WORKER_DEQUEUE_TIMEOUT_SECONDS", "5"))
    repository = create_packet_repository()
    queue = create_job_queue()
    provider_registry = create_provider_registry()
    workflow_service = ClaimPacketWorkflowService(repository=repository, provider_registry=provider_registry)
    processor = JobProcessor(workflow_service)
    providers = {provider["kind"]: provider["name"] for provider in workflow_service.active_provider_payload()}
    print(
        (
            f"NeuroDocOps worker started with {repository.__class__.__name__}, {queue.__class__.__name__}, "
            f"ocr={providers.get('ocr')}, extraction={providers.get('extraction')}."
        ),
        flush=True,
    )
    while True:
        process_next_job(queue, processor, timeout_seconds=dequeue_timeout_seconds)


if __name__ == "__main__":
    main()
