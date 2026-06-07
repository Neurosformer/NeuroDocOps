# NeuroDocOps First Surface Operating Model

Date: 2026-06-07

## Purpose

This document turns the current UI, RBAC, provider registry, API, worker, and docs into a concrete first-version operating model. The goal is to stop treating the app as cosmetic screens and make every screen answer a real operator question:

> Who is using this, what task are they doing, which backend service executes it, which provider may be plugged in later, and what document proves the workflow works?

NeuroDocOps is not a generic OCR dashboard. The first surface is a claims packet evidence-preparation workstation plus API/worker backend.

## First Surface

The first usable product surface should support one narrow workflow:

```text
claim packet arrives
  -> intake specialist creates packet and attaches documents
  -> worker parses/classifies/extracts fields
  -> reviewer resolves missing/low-confidence evidence
  -> manager releases approved export
  -> auditor verifies the trail
  -> integration account sends/receives data from external systems
```

The first surface should not include broad analytics, autonomous claim decisions, payment approval, fraud scoring, or generic document chat.

## Users, Roles, And Real Tasks

| User Type | Current RBAC Role | Real-World Person Or System | Primary Tasks | Should Not Do |
| --- | --- | --- | --- | --- |
| System owner | `admin` | Internal product/operator admin | Configure environment, provider mode, users, tenants later, emergency support, inspect system readiness | Daily packet review as default workflow |
| Claims ops lead | `manager` | Team lead, queue owner, BPO/TPA supervisor | Monitor queue, assign review tasks, adjust priority/due dates, approve final export, check SLA/rework risk manually | Change infrastructure/provider secrets |
| Evidence reviewer | `reviewer` | Claims reviewer, intake QA, nurse/medical reviewer depending workflow | Review extracted fields, resolve exceptions, request missing evidence, approve packet for release | Export final data without manager/admin permission |
| Compliance auditor | `auditor` | QA/compliance reviewer, client oversight, internal audit | Read packets, audit events, provider decisions, review history | Mutate packet data or run processing |
| External system | `integration` | Claims system, TPA portal, BPO intake pipeline, SFTP/email ingest service | Create/read packets through API, trigger processing, poll jobs, export approved structured result | Act as a human reviewer or read audit by default |

`admin` can technically perform integration actions, but production automation should use `integration` because it is safer, easier to audit, and follows least privilege.

## First-Version Functionalities

| Functionality | User | Current Status | Backend Owner | Next Real Step |
| --- | --- | --- | --- | --- |
| Login/persona selection | All | Dev RBAC login sends `X-Actor` and `X-Role` | `services/web`, `packages/security` | Replace with real auth provider later, preserve role matrix |
| Packet intake | Manager, reviewer, integration | API and UI create packets with source-file upload and optional fallback text | `services/api`, `packages/workflow` | Add intake connectors later |
| Source document storage | Manager, reviewer | Backend has object store boundary, MinIO, and source preview/download endpoint | `packages/storage`, `services/api` | Add richer page-level preview and OCR artifacts |
| Processing job | Manager, reviewer, integration | Redis worker processes packet job | `services/worker`, `packages/jobs` | Add retry/error display and provider artifact persistence |
| OCR/document parsing | Worker | Mock OCR plus local digital-PDF text extraction for embedded-text PDFs | `packages/providers` | Add OCR router/cache and scanned-document OCR experiments later |
| Classification/extraction | Worker/API | Deterministic insurance rules plus reviewer field correction | `packages/providers`, `packages/workflow` | Add better provider fixtures and page-level citations |
| Completeness checklist and review queue | Reviewer, manager | Rules create packet review tasks; tasks can be resolved/reopened, assigned, prioritized, given due dates, and filtered in the review queue | `packages/workflow`, `services/api`, `services/web` | Add SLA/escalation automation, notifications, and saved queues |
| Human approval | Reviewer, manager | Packet approval requires all open review tasks to be resolved first | `packages/workflow` | Add reject/request-change taxonomy and manager release policy |
| Export | Manager, admin, integration | Approved JSON export only | `services/api`, `packages/workflow` | Add versioned export schema, CSV, webhook export later |
| Audit trail | Auditor, manager, reviewer | Audit endpoint exists | `packages/workflow`, storage repo | Add correction/provider/job events and audit filters |
| System status | Admin, manager | `/ready` reports live provider metadata | `services/api`, provider registry | Add provider config page/read-only first |

## Service And Plugin Boundaries

NeuroDocOps should plug services at the backend boundary, not directly inside React components. The frontend should call NeuroDocOps API endpoints; the API/worker should choose providers through interfaces.

The table below is a first-surface plugin map. "Current Provider" means implemented or directly wired in the current MVP foundation. "Future" interfaces are roadmap boundaries and should not be described as available product features until they exist in code and tests.

| Plugin Area | Interface Or Package | Current Provider | First Practical Plug | Paid/Enterprise Plug Later | Where It Plugs In |
| --- | --- | --- | --- | --- | --- |
| OCR/document parsing | `OCRProvider`, future `DocumentParserProvider` | `MockOCRProvider`; local digital-PDF text extraction for embedded text | Tesseract/Paddle/Surya experiment for scanned/simple pages | Azure Document Intelligence, AWS Textract, Google Document AI, LlamaParse, ABBYY | Worker/provider router |
| Extraction/reasoning | `ExtractionProvider`, future `ReasoningProvider` | `RuleBasedInsuranceExtractionProvider` | Rule fixtures plus local deterministic extraction | OpenAI/Claude/Gemini/Azure OpenAI structured extraction | Worker/provider router |
| Object storage | `ObjectStore` | In-memory, MinIO | MinIO for local/pilot | S3, Azure Blob, GCS, customer bucket | API upload/download and worker artifact reads |
| Packet database | `PacketRepository` | In-memory, Postgres JSONB | Postgres | Managed Postgres/RDS/Cloud SQL | API/workflow repository |
| Queue/jobs | `JobQueue` | In-memory, Redis | Redis | Managed Redis, SQS, Cloud Tasks, Celery/Dramatiq | API enqueue, worker consume |
| Auth/identity | `packages/security` today, future `IdentityProvider` | Dev headers | Keycloak for self-hosted pilot | Auth0, Cognito, Azure Entra ID, customer SSO | API dependency and web login |
| Search | Future `SearchProvider` | None | Postgres full-text | OpenSearch, Elasticsearch, Meilisearch/vector DB | API search endpoint, worker indexing |
| Intake | Future `IntakeProvider` | Manual web/API | SFTP folder, email parser, webhook | Graph API, Gmail API, customer claims portal API | Separate ingest worker/API route |
| Telemetry | Future `TelemetryProvider` | Local logs | OpenTelemetry local/Grafana | Sentry, Datadog, customer SIEM | API/worker instrumentation |
| Secrets/config | Provider settings/env | `.env` | Docker secrets/local env | Doppler, AWS Secrets Manager, Azure Key Vault | App startup/provider registry |
| Export delivery | Future `ExportProvider` | API JSON response | CSV/JSON file in object store | Webhook, SFTP, Guidewire/Duck Creek adapter | Worker export job/API trigger |

For the detailed plugin/provider strategy, fit-test gates, and provider tier model, see `docs/pluggable-provider-development-plan.md` and `docs/pluggable-provider-test-plan.md`. For the runtime path across API, worker, web, storage, providers, RBAC, audit, and export, see `docs/system-flow.md`.

## API Versus Provider Rule

Use this decision rule:

| Need | Build As |
| --- | --- |
| Human/product action such as create packet, review, approve, export | NeuroDocOps API endpoint |
| Long-running processing such as OCR, extraction, export delivery | Worker job |
| Vendor/cloud/service-specific capability | Provider adapter behind package interface |
| External customer system pushing/pulling data | Integration API or webhook provider |
| UI state or presentation | React component only, never workflow truth |

This keeps the UI from becoming a fake control panel and keeps paid/cloud vendors out of the workflow core.

## First Documents To Test Version 1

We need real-looking documents before adding more providers. Do not use private or customer-confidential files without permission.

Start with these document categories:

| Packet Type | Documents Needed | Where To Source Safely |
| --- | --- | --- |
| Auto claim packet | Claim form, incident/police-style report, repair estimate/invoice, vehicle photos metadata, driver ID | Public sample insurance forms, state/DMV accident report samples, synthetic repair invoices, generated ID placeholder |
| Property claim packet | Claim form, proof of loss, contractor estimate, photos metadata, policy declaration sample | Public carrier sample proof-of-loss forms, synthetic contractor invoice, public policy declaration templates |
| Medical/injury packet | Claim form, medical bill, treatment note, EOB-style statement, identity evidence | CMS/public EOB examples, synthetic medical bill, de-identified public sample forms |
| Workers compensation/disability | First report of injury, employer statement, medical note, wage statement | Public state workers-comp forms and synthetic wage statement |

Create a benchmark manifest for each packet:

```text
packet_id
packet_type
documents[]
expected_document_class
expected_fields[]
required_evidence[]
known_missing_evidence[]
expected_review_tasks[]
```

The first benchmark does not need paid OCR. It can start with text fixtures derived from public/synthetic documents, then add PDFs once local PDF text extraction exists.

## DevOps Team Workflow

Use the project-local agents as a team, not as random assistants:

1. DevOps Lead defines the slice and handoff.
2. Research Agent finds public documents/providers and writes source notes.
3. API/RBAC Engineer turns the slice into endpoints, permissions, and tests.
4. Worker/Infrastructure Engineer wires queue/storage/provider execution.
5. UI/UX Designer exposes only real backend-backed actions.
6. QA/Release Engineer runs regression, stack smoke, and acceptance tests.
7. Docs/Product Engineer updates API/product/runbooks with implemented-vs-roadmap status.

## Immediate First Real Slice

Build this next before adding more dashboard polish:

1. Add a benchmark fixture folder with synthetic/public text documents and a manifest.
2. Add a document-source research note listing where each sample came from and whether it is public/synthetic.
3. Add local PDF text extraction provider or, if too large for the next slice, add the benchmark manifest and fixture runner first.
4. Add document preview/download endpoint for uploaded source files.
5. Add field correction endpoint and audit event.
6. Update frontend to show source document, extracted field, correction input, and audit entry.

Acceptance criteria:

- No paid OCR/model call is required.
- A reviewer can correct an extracted field.
- The correction appears in export.
- Audit shows who changed the field.
- The sample packet source is documented.
