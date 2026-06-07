# NeuroDocOps System Flow

Date: 2026-06-08

## Purpose

This document describes the current insurance claims packet MVP runtime flow across the web console, API service, worker service, workflow rules, storage, provider/plugin boundaries, development RBAC, audit, and export.

It separates implemented behavior from roadmap provider areas so the product stays real and does not become cosmetic UI around unsupported claims.

## Scope

Implemented MVP foundation:

- FastAPI API service.
- Worker service for queued packet-processing jobs.
- React/Vite reviewer console.
- Claim packet workflow service.
- Development RBAC headers.
- In-memory defaults for tests/local one-process runs.
- Optional local Postgres, Redis, and MinIO through configured backends.
- Source-document upload and source preview/download.
- Local digital-PDF text extraction for PDFs with embedded text.
- Mock OCR and rule-based insurance extraction for deterministic local/test flows.
- Review tasks, task-level resolve/reopen, field correction, approval gate, JSON export, and audit events.

Roadmap / not production-ready:

- Production auth, tenant isolation, SSO, and token validation.
- OCR for scanned PDFs, images, handwriting, forms, tables, and mixed document bundles.
- LLM reasoning providers.
- Search providers.
- Intake connectors such as email, SFTP, webhooks, or claims-system portals.
- Telemetry/cost providers beyond local logs/readiness metadata.
- Secret-manager providers.
- Export delivery providers such as CSV artifacts, webhooks, SFTP, or Guidewire/Duck Creek adapters.

## Actors And RBAC Context

Current development roles:

| Role | Current Use |
| --- | --- |
| `admin` | Local/system operator with all permissions |
| `manager` | Create/read/process/review/export/audit/job access |
| `reviewer` | Create/read/process/review/audit/job access; no export |
| `auditor` | Read packets, audit, and jobs only |
| `integration` | API automation for create/read/process/export/jobs; no human review or audit read |

Current auth mechanism:

- API reads `X-Actor` and `X-Role`.
- Missing headers default to `dev-admin` / `admin` for local compatibility.
- This is development RBAC only.
- Real auth, tenant isolation, SSO, and identity-provider integration are roadmap.

## High-Level Runtime Flow

```text
web console or integration client
  -> API receives packet/document/review/export request
  -> API checks development RBAC headers
  -> workflow service validates packet state transition
  -> repository persists packet/audit/job state
  -> object store stores or retrieves source bytes when uploaded
  -> job queue enqueues long-running processing when requested
  -> worker consumes job
  -> worker invokes configured OCR/extraction providers
  -> workflow records extracted fields, review tasks, audit events
  -> reviewer resolves/corrects evidence
  -> manager/admin/integration requests export after approval
  -> API returns approved JSON export
```

## Flow 1: Packet Intake

Implemented:

1. User or integration client creates a claim packet through `POST /claim-packets`.
2. API checks `packet:create` permission from development RBAC headers.
3. Workflow service creates packet state.
4. Packet repository persists the packet.
5. Audit event records packet creation.

Current storage options:

- In-memory repository by default.
- Postgres JSONB repository when `NEURODOCOPS_STORAGE_BACKEND=postgres` and `DATABASE_URL` are set.

Implemented review queue behavior:

- Intake providers for SFTP, email, webhook, Graph API, Gmail API, and customer claims portals.
- Tenant-aware intake routing.

## Flow 2: Source Document Upload And Object Storage

Implemented:

1. Client uploads source document through `POST /claim-packets/{packet_id}/documents`.
2. API checks upload permission.
3. API stores bytes in configured `ObjectStore`.
4. API attaches source object metadata to the document record.
5. Packet repository persists updated packet.
6. Source document can be downloaded through `GET /claim-packets/{packet_id}/documents/{document_id}/source`.

Current object-store options:

- In-memory object store for tests/local one-process runs.
- MinIO when `NEURODOCOPS_OBJECT_STORAGE_BACKEND=minio` and `OBJECT_STORAGE_*` variables are set.

Current behavior:

- Uploaded source bytes are stored in the configured object store.
- Digital PDFs with embedded text can be parsed locally when the local PDF text provider is enabled.
- The request `text` field remains useful as an override/fallback and for non-PDF, scanned, image-only, or demo documents.

Current limitation:

- Local PDF text extraction is not OCR. It does not read scanned pages, images, handwriting, checkboxes, signatures, or tables.

Roadmap:

- Page-level OCR artifacts.
- Source preview with richer page/citation inspection.
- OCR/layout providers for scanned PDFs, images, forms, and tables.
- S3, Azure Blob, GCS, or customer bucket adapters.

## Flow 3: Processing Through API Or Worker

Implemented synchronous/control-plane endpoints:

- `POST /claim-packets/{packet_id}/classify`
- `POST /claim-packets/{packet_id}/extract`
- `POST /claim-packets/{packet_id}/checklist`

Implemented queued/data-plane endpoint:

- `POST /claim-packets/{packet_id}/process`

Queued flow:

1. API checks process permission.
2. API enqueues a packet-processing job through `JobQueue`.
3. Redis-backed queue is used when `NEURODOCOPS_JOB_QUEUE_BACKEND=redis` and `REDIS_URL` are set.
4. Worker consumes the job.
5. Worker runs requested steps.
6. Job status can be read through `GET /jobs/{job_id}`.

Current queue options:

- In-memory queue for tests/local one-process runs.
- Redis for local stack worker-backed processing.

Roadmap:

- Retry policies.
- Batch processing.
- Large-file processing.
- Export jobs.
- Managed queues such as SQS or Cloud Tasks.

## Flow 4: OCR / Document Parsing Providers

Implemented:

- `OCRProvider` contract exists.
- `MockOCRProvider` keeps local/test processing deterministic.
- Local digital-PDF text extraction can parse embedded text from source PDFs without a paid OCR call.
- Provider metadata is reported through `/ready` without exposing secrets.

Current limitation:

- Local PDF text extraction is source-byte parsing, not scanned-image OCR.
- Image-only PDFs, photos, handwriting, complex forms, tables, checkboxes, and signatures remain outside the implemented local parser.

Safe default:

- No paid OCR is required for local development, tests, or benchmark fixture runs.
- Paid/live OCR providers must remain disabled unless explicitly enabled through provider-specific configuration and live-provider flags.

Roadmap:

- OCR router/cache keyed by checksum and provider settings.
- Optional open-source OCR.
- Paid OCR/document parsing providers only when explicitly enabled and fit-tested.

Provider safety rule:

- Paid OCR must not run unless live-provider configuration is explicit.
- Low-confidence or failed OCR should create review tasks or job errors, not silent success.

## Flow 5: Extraction / Reasoning Providers

Implemented:

- `ExtractionProvider` contract exists.
- `RuleBasedInsuranceExtractionProvider` performs deterministic classification/extraction for the insurance claims packet MVP.
- Extracted fields include confidence and citation-oriented metadata.
- Reviewer corrections persist and appear in export.

Roadmap:

- `ReasoningProvider` or structured LLM extraction provider.
- Provider scorecards and fit tests before any LLM route becomes default.
- Page-level citations and richer table extraction.

Safety rule:

- Provider output assists review; it does not replace human approval.
- Extraction uncertainty should route to review tasks.

## Flow 6: Review Tasks, Corrections, And Human Approval

Implemented:

1. Checklist evaluation creates review tasks for missing evidence or low-confidence items.
2. Reviewers/managers can resolve or reopen individual tasks.
3. Reviewers can correct extracted fields.
4. Corrections are recorded with actor identity from `X-Actor`.
5. Packet approval is blocked while review tasks remain open.
6. Export requires an approved packet.

Current roles:

- `reviewer`, `manager`, and `admin` can complete review actions.
- `reviewer` cannot export.
- `auditor` cannot mutate packet data.
- `integration` cannot perform human review.

Roadmap:

- Review tasks carry assignee, priority, and due-date metadata for queue ownership.
- Review queues can be filtered by assignment, status, priority, and due-date fields.

Roadmap:

- SLA breach detection, automatic escalation, notifications, and saved/shared queues remain roadmap.
- Reject/request-change taxonomy.
- Manager release policy.

## Flow 7: Audit Trail

Implemented:

- Audit endpoint exists.
- Audit events are persisted with packet state.
- Field corrections and review task actions emit audit events.
- Audit reads are RBAC-protected.

Current audit access:

- `admin`, `manager`, `reviewer`, and `auditor` can read audit.
- `integration` does not read audit by default.

Roadmap:

- Provider-call audit/cost events.
- Job failure audit filters.
- Tenant-aware audit filtering.
- Audit export/reporting.

Audit principle:

- Every provider-backed or human-backed state change should eventually be reconstructable from audit, packet state, job status, and provider metadata.

## Flow 8: Export

Implemented:

1. Export request is made through `POST /claim-packets/{packet_id}/export`.
2. API checks export permission.
3. Workflow verifies approval state.
4. API returns approved structured JSON.
5. Export action is audit-recorded.

Current export permissions:

- `admin`, `manager`, and `integration` can export.
- `reviewer` and `auditor` cannot export.

Current limitation:

- Export delivery is API JSON only.

Roadmap:

- Versioned export schema.
- CSV export.
- Export artifacts in object storage.
- Webhook/SFTP/claims-system delivery providers.
- Guidewire/Duck Creek adapters later.

Safety rule:

- Human approval before export remains mandatory for the claims packet MVP.

## Flow 9: Search, Intake, Telemetry, Secrets, And Config

Search:

- Current status: not implemented.
- Roadmap: `SearchProvider`, starting with Postgres full-text, later OpenSearch/Elasticsearch/Meilisearch/vector DB.

Intake:

- Current status: manual web/API packet creation.
- Roadmap: `IntakeProvider` for email, SFTP, webhooks, Graph API, Gmail API, customer portal APIs.

Telemetry:

- Current status: local logs and safe readiness metadata.
- Roadmap: `TelemetryProvider` for provider calls, cost estimates, latency, failures, Sentry/OpenTelemetry/customer SIEM.

Secrets/config:

- Current status: environment variables and local Compose config.
- Roadmap: `SecretProvider` for Doppler, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, Docker secrets.

Config safety:

- `/ready` may report safe provider names, tiers, live flags, and adapter status.
- It must not expose credentials, database URLs, Redis URLs, object keys, or storage secrets.

## Implemented Vs Roadmap Matrix

| Area | Implemented Today | Roadmap |
| --- | --- | --- |
| API | Packet/document/review/job/audit/export endpoints | Tenant-aware API surface |
| Web | Reviewer console and source-upload intake | Richer viewer, queue ownership |
| Worker | Consumes queued packet-processing jobs | Retries, large batch jobs, export jobs |
| Storage | In-memory and Postgres repository | Normalized repos, managed databases |
| Object storage | In-memory and MinIO | S3/Azure Blob/GCS/customer buckets |
| Queue | In-memory and Redis | Managed queues |
| OCR/parsing | Contract, mock provider, local digital-PDF text extraction | Scanned/image OCR, layout parsers, cloud parsers |
| Extraction | Rule-based insurance provider | LLM/reasoning providers |
| RBAC/auth | Dev headers | Real auth, tenant isolation, SSO |
| Audit | Packet/review/correction/export events | Provider/job/cost audit filters |
| Export | Approval-gated JSON response | CSV, object artifacts, webhooks, SFTP |
| Search | Not implemented | Postgres full-text and search providers |
| Intake | Manual/API | Email/SFTP/webhook/customer systems |
| Telemetry | Local logs/readiness metadata | Provider cost/error/latency telemetry |
| Secrets | Env vars | Secret-manager providers |

## Local Stack Commands

```bash
python scripts/server_switch.py on
python scripts/server_switch.py status
python scripts/server_switch.py logs
python scripts/server_switch.py off
```

The local stack uses Postgres, Redis, and MinIO, but still keeps paid OCR/model providers disabled unless explicitly configured.

## Provider/Plugin Safety Rules

1. Local/free providers are the default.
2. Paid providers are opt-in only.
3. Unit tests and stack smoke tests must not require paid credentials.
4. Provider outputs must normalize into NeuroDocOps packet/document/field/citation/review/audit concepts.
5. Provider failures must become explicit job errors, review tasks, audit events, or telemetry events.
6. Providers must not bypass RBAC.
7. Providers must not bypass human approval before export.
8. Readiness/config endpoints must not leak secrets.
9. Web UI must display backend-supported state only.
10. Vigolium-inspired UI direction is inspiration for seriousness and evidence orientation only; no copied assets, layouts, logos, screenshots, or proprietary text.
