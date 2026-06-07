# NeuroDocOps Infra

This directory defines the first service-oriented local runtime:

- `api`: FastAPI control-plane service.
- `worker`: background worker for queued packet-processing jobs.
- `web`: reviewer console.
- `postgres`: system-of-record database when `NEURODOCOPS_STORAGE_BACKEND=postgres` is enabled.
- `redis`: queue/broker for packet-processing jobs.
- `minio`: S3-compatible object storage for original documents, OCR artifacts, and exports.

Only the user-facing services are published to the host by default: API `8000`, web `5173`, MinIO API `9000`, and MinIO console `9001`. Postgres and Redis stay on the internal Compose network to avoid local port conflicts.

Run from this directory:

```bash
docker compose up --build
```

The API and worker use the in-memory `PacketRepository`, object store, and job queue by default for one-process local runs. This compose stack sets `NEURODOCOPS_STORAGE_BACKEND=postgres`, so packet and audit snapshots are stored in Postgres through the shared repository boundary. It sets `NEURODOCOPS_JOB_QUEUE_BACKEND=redis`, so `POST /claim-packets/{packet_id}/process` enqueues jobs consumed by the worker. It also sets `NEURODOCOPS_OBJECT_STORAGE_BACKEND=minio`, so `POST /claim-packets/{packet_id}/documents` stores uploaded source bytes in MinIO while packet metadata stays in Postgres.
