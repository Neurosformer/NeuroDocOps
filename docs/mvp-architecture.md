# MVP Architecture

NeuroDocOps starts as an insurance claims packet workflow engine, not a generic PDF chat app or raw OCR API. The first implementation proves the core product loop: packet intake, document classification, field extraction, checklist evaluation, human review, approval, export, and audit.

## Current Components

```text
services/web
  -> services/api
      -> packages/workflow ClaimPacketWorkflowService
      -> packages/domain Pydantic models
      -> packages/providers OCRProvider and ExtractionProvider contracts
      -> packages/storage PacketRepository boundary
          -> in-memory repository for tests/local runs
          -> Postgres JSONB repository for shared durable state
      -> packages/storage ObjectStore boundary
          -> in-memory object store for tests/local runs
          -> MinIO object store for uploaded source documents
       -> packages/jobs JobQueue boundary
           -> in-memory queue for tests/local runs
           -> Redis queue for worker-backed packet processing
      -> packages/security RBAC boundary
          -> development header checks for actor and role permissions
  -> services/worker consumes queued packet-processing jobs
  -> infra/postgres, redis, minio for persistence, processing, and object storage milestones
```

The API, worker, web, database, queue, and object-storage boundaries are now explicit. The workflow service no longer owns packet dictionaries directly; it depends on a `PacketRepository` contract. Local tests can keep using the in-memory repository, in-memory object store, and in-memory job queue, while Docker/runtime environments can set `NEURODOCOPS_STORAGE_BACKEND=postgres`, `NEURODOCOPS_OBJECT_STORAGE_BACKEND=minio`, and `NEURODOCOPS_JOB_QUEUE_BACKEND=redis` to use shared Postgres state, MinIO source-document storage, and Redis-backed worker processing. Production OCR/model providers remain the next infrastructure step.

The provider boundary is already present:

- `OCRProvider` normalizes OCR/layout output from a source document.
- `ExtractionProvider` classifies documents and returns extracted fields with citations.
- `MockOCRProvider` keeps tests deterministic while preserving the future Azure/Google/AWS adapter shape.
- `RuleBasedInsuranceExtractionProvider` contains the current deterministic insurance rules and can be replaced by provider + LLM extraction later.

Provider selection should be tiered rather than hardcoded. The proof-of-concept defaults to free/local providers; paid providers are opt-in. The long-term architecture supports `mock`, `local`, `paddle`, `surya`, `llamaparse`, `azure`, `aws`, `google`, and enterprise providers behind the same contracts. The full provider development plan is documented in `docs/pluggable-provider-development-plan.md`.

## Service Boundaries

- `services/api`: control plane for tenant-scoped packet lifecycle, review, approval, export requests, and audit reads.
- `services/worker`: data plane for queued OCR, extraction, checklist, export, and retry jobs.
- `services/web`: reviewer console; owns no workflow truth.
- `packages/domain`: shared domain schemas and enums.
- `packages/workflow`: claim packet workflow rules and state transitions.
- `packages/providers`: OCR/extraction adapter contracts and current mock/rule-based providers.
- `packages/storage`: repository/object-store contracts plus in-memory, Postgres, and MinIO implementations.
- `packages/jobs`: queue contracts plus in-memory and Redis implementations.
- `packages/security`: current development RBAC primitives; future auth, identity, tenant, and permission provider contracts.
- Future `packages/search`: Postgres full-text, OpenSearch, Meilisearch, and vector provider contracts.
- Future `packages/telemetry`: provider usage, cost, logging, and error reporting contracts.
- `infra/postgres`: system of record for packet and audit snapshots when the Postgres repository is enabled.
- `infra/redis`: queue/broker for packet-processing jobs.
- `infra/minio`: source document storage now; future OCR artifact and export storage.

## Product Loop

1. Create a claim packet with claim metadata and OCR text for each source document.
2. Classify included documents such as claim forms, incident reports, identity evidence, medical bills, repair invoices, and policy documents.
3. Extract structured fields with confidence scores and document-level citations.
4. Evaluate the packet completeness checklist.
5. Create review tasks for missing evidence and low-confidence fields.
6. Resolve review tasks and approve the packet.
7. Export approved structured data.
8. Preserve audit events for intake, classification, extraction, checklist evaluation, review, and export.

## Current Workflow API

```text
POST /claim-packets
GET  /claim-packets
GET  /claim-packets/{packet_id}
POST /claim-packets/{packet_id}/documents
POST /claim-packets/{packet_id}/classify
POST /claim-packets/{packet_id}/extract
POST /claim-packets/{packet_id}/checklist
POST /claim-packets/{packet_id}/process
POST /claim-packets/{packet_id}/review
POST /claim-packets/{packet_id}/export
GET  /jobs/{job_id}
GET  /claim-packets/{packet_id}/audit
```

Protected workflow endpoints check `X-Actor` and `X-Role` through the current RBAC layer. Missing headers default to local `dev-admin`/`admin` for compatibility; production auth and tenant enforcement remain future work.

Local stack control is centralized in `scripts/server_switch.py`:

```bash
python scripts/server_switch.py on
python scripts/server_switch.py status
python scripts/server_switch.py logs
python scripts/server_switch.py off
```

## Next Infrastructure Decisions

- Add source document download/preview endpoints and page-image storage.
- Add a provider configuration registry and OCR router/cache before enabling live paid OCR.
- Add local PDF text extraction first, then benchmark Azure Document Intelligence, LlamaParse, Google Document AI, AWS Textract, and open-source OCR on real claim packets.
- Expand async processing for large files, batches, retries, and export jobs.
- Replace development header RBAC with tenant-aware authentication, role-based access control, and identity-provider integration.
- Add export jobs for CSV, Excel, JSON, webhooks, and claims-system API integrations.
