# API Guide

The MVP API is packet-first and models the first wedge: insurance claims document packets. It defaults to an in-memory `PacketRepository`, in-memory object store, and in-memory job queue for local/test runs. It can use a JSONB-backed Postgres repository when `NEURODOCOPS_STORAGE_BACKEND=postgres` and `DATABASE_URL` are set, a Redis worker queue when `NEURODOCOPS_JOB_QUEUE_BACKEND=redis` and `REDIS_URL` are set, and MinIO source-document storage when `NEURODOCOPS_OBJECT_STORAGE_BACKEND=minio` plus `OBJECT_STORAGE_*` variables are set. Storage, OCR, extraction, objects, and jobs sit behind provider/repository/object-store/queue contracts, with deterministic mock/rule-based implementations used for local development.

Run locally:

```bash
uvicorn services.api.neurodocops_api.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Readiness check with active provider metadata:

```bash
curl http://localhost:8000/ready
```

The readiness payload reports safe provider names, tiers, live flags, and adapter status. It does not expose provider credentials, storage secrets, database URLs, Redis URLs, or object keys.

## Authentication And RBAC Headers

The current MVP uses development RBAC headers on protected endpoints:

```bash
-H 'X-Actor: reviewer@example.com' \
-H 'X-Role: reviewer'
```

If headers are omitted, the API defaults to `dev-admin` with role `admin` for local compatibility. Unsupported roles or insufficient permissions return `403`.

Current role matrix:

| Role | Permissions |
| --- | --- |
| `admin` | All permissions |
| `manager` | Create/read packets, upload documents, process packets, complete reviews, export packets, read audit, read jobs |
| `reviewer` | Create/read packets, upload documents, process packets, complete reviews, read audit, read jobs; no export |
| `auditor` | Read packets, read audit, read jobs only |
| `integration` | Create/read packets, process packets, export packets, read jobs; no upload, review, or audit read |

One-click local stack startup:

```bash
python scripts/server_switch.py on
```

Create a claim packet:

```bash
curl -X POST http://localhost:8000/claim-packets \
  -H 'Content-Type: application/json' \
  -H 'X-Actor: manager@example.com' \
  -H 'X-Role: manager' \
  -d '{
    "claim_reference":"CLM-1001",
    "claimant_name":"Amina Rahman",
    "loss_type":"auto",
    "documents":[
      {"filename":"claim-form.pdf","text":"Claim form for claim number CLM-1001 and policy number POL-42."},
      {"filename":"incident-report.pdf","text":"Incident report for accident with loss date 2026-05-01."},
      {"filename":"identity.pdf","text":"Passport identity document for claimant Amina Rahman."},
      {"filename":"repair-invoice.pdf","text":"Repair invoice for vehicle damage. Amount due 1250 USD."}
    ]
  }'
```

Create a packet shell, then upload source documents:

```bash
curl -X POST http://localhost:8000/claim-packets \
  -H 'Content-Type: application/json' \
  -d '{"claim_reference":"CLM-1002","claimant_name":"Amina Rahman","loss_type":"auto"}'

curl -X POST http://localhost:8000/claim-packets/{packet_id}/documents \
  -H 'X-Actor: manager@example.com' \
  -H 'X-Role: manager' \
  -F 'file=@claim-form.pdf;type=application/pdf' \
  -F 'text=Claim form for claim number CLM-1002 and policy number POL-42.' \
  -F 'metadata={"source":"api-guide"}'
```

The upload endpoint stores source bytes in the configured object store and attaches object metadata to the packet document. The `text` field is still required until a real OCR adapter reads source bytes directly.

Preview or download the stored source bytes for an uploaded document:

```bash
curl http://localhost:8000/claim-packets/{packet_id}/documents/{document_id}/source \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer' \
  --output source-document.pdf
```

Text-payload documents created directly in the packet body do not have source bytes. Uploaded documents include `source_object` metadata and can be opened from the reviewer console.

Run the workflow:

```bash
curl -X POST http://localhost:8000/claim-packets/{packet_id}/classify \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer'
curl -X POST http://localhost:8000/claim-packets/{packet_id}/extract \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer'
curl -X POST http://localhost:8000/claim-packets/{packet_id}/checklist \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer'
curl -X POST http://localhost:8000/claim-packets/{packet_id}/review \
  -H 'Content-Type: application/json' \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer' \
  -d '{"decision":"approve","reviewer":"claims.ops@example.com","notes":"Validated evidence."}'
curl -X POST http://localhost:8000/claim-packets/{packet_id}/export \
  -H 'X-Actor: manager@example.com' \
  -H 'X-Role: manager'
```

Correct an extracted field before approval. The API records the authenticated `X-Actor` as the correction actor in the audit trail:

```bash
curl -X POST http://localhost:8000/claim-packets/{packet_id}/documents/{document_id}/fields/claim_number/correct \
  -H 'Content-Type: application/json' \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer' \
  -d '{"value":"CLM-1001-A","reviewer":"reviewer@example.com","notes":"Corrected against source document."}'
```

Queue packet processing through the worker:

```bash
curl -X POST http://localhost:8000/claim-packets/{packet_id}/process \
  -H 'Content-Type: application/json' \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer' \
  -d '{"steps":["classify","extract","checklist"]}'

curl http://localhost:8000/jobs/{job_id} \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer'
```

View audit events:

```bash
curl http://localhost:8000/claim-packets/{packet_id}/audit \
  -H 'X-Actor: auditor@example.com' \
  -H 'X-Role: auditor'
```

## Local Benchmark Fixture

The first benchmark packet lives under `benchmarks/claim_packets/auto_claim_v1/`. It uses synthetic text documents and expected field labels, with public-source guidance in `benchmarks/claim_packets/SOURCE_NOTES.md`.

Run the fixture against safe local providers only:

```bash
python3 scripts/run_benchmark_fixture.py
```

The runner uses `MockOCRProvider` and `RuleBasedInsuranceExtractionProvider`; it makes no paid OCR or model calls.
