# NeuroDocOps

**AI Document Operations for Regulated Workflows**

NeuroDocOps is the core Neurosformer platform: an AI document operations layer for regulated, document-heavy industries. It helps teams convert PDFs, scanned files, forms, invoices, contracts, evidence bundles, compliance reports, and business records into structured, reviewable, searchable, auditable workflow data.

The product is not a generic "chat with PDF" tool. The opportunity is workflow transformation: document ingestion, OCR, classification, extraction, citations, human review, compliance checklists, approvals, audit logs, exports, and API integration.

## Global Opportunity

Document-heavy industries across the US, Canada, UK, EU, Singapore, UAE, India, Germany, the Netherlands, and Australia face high labor cost, strict compliance pressure, and growing pressure to turn AI pilots into scaled operational impact.

NeuroDocOps should target organizations that already spend money on document review, compliance operations, back-office automation, and enterprise workflow tools.

## Target Industries

| Market | High-value workflows |
| --- | --- |
| Insurance | Claims files, medical bills, evidence review, fraud indicators, policy documents |
| Finance and Banking | KYC, AML, loan files, onboarding documents, compliance reports |
| Legal and Compliance | Contracts, discovery files, policy comparison, regulatory evidence |
| Logistics and Trade | Bills of lading, invoices, customs documents, shipment packs |
| Healthcare Administration | Referral letters, lab reports, insurance documents, discharge packets |
| Enterprise Procurement | Purchase orders, vendor documents, invoices, supplier records |

## Problem

Regulated teams still manage critical documents through email folders, shared drives, spreadsheets, manual review queues, and disconnected business systems.

Common pain points include:

- Slow document review and approval cycles
- Manual data entry into ERPs, CRMs, claims systems, HR systems, and accounting tools
- Missing fields, inconsistent formatting, duplicate records, and low data quality
- Difficult audit preparation and weak evidence traceability
- Poor search across historical document archives
- Limited visibility into process bottlenecks and exception patterns
- High dependency on staff memory and manual filing systems

## Solution

NeuroDocOps provides an AI-powered document operations workflow that can ingest documents, classify them, extract structured fields, answer questions with source citations, route low-confidence items to human review, and export approved data to downstream systems.

## MVP Scope

The first product wedge is **Insurance Claims Packet Ops**. It focuses on claim packets that contain claim forms, incident reports, identity evidence, medical bills, repair invoices, policy documents, photos, and correspondence.

The product and market rationale are documented in `docs/market-validation.md`. The short version: NeuroDocOps should win as a human-in-the-loop claims evidence operations layer, not as a generic OCR or AI document dashboard.

The MVP workflow:

1. Intake a claim packet with claim metadata and source documents
2. Classify each document in the packet
3. Extract key fields with confidence scores and source citations
4. Evaluate a claim completeness checklist
5. Create review tasks for missing evidence and low-confidence fields
6. Require human approval before export
7. Export approved structured data for downstream claims systems
8. Maintain audit logs for intake, classification, extraction, checklist evaluation, review, and export

## Product Capability Map

Implemented MVP foundation:

- Claim packet intake through API and current web console.
- Source-document upload to the configured object store, with source preview/download.
- Local digital-PDF text extraction for PDFs that already contain embedded text.
- Deterministic document classification and field extraction for insurance claim packet fixtures.
- Review tasks, task-level resolve/reopen, field correction, human approval gate, JSON export, and audit events.
- Development RBAC headers for local/test role simulation.
- In-memory defaults with optional Postgres, Redis, and MinIO local stack.
- Safe provider metadata through `/ready` without exposing secrets.

Current limitations:

- Local PDF text extraction is not scanned-document OCR and does not read image-only PDFs, photos, handwriting, complex forms, or tables.
- Pasted evidence text remains useful for non-PDF files, scanned PDFs, demos, and deterministic fixtures.
- Production auth, tenant isolation, SSO, live OCR, LLM reasoning, search, and export-delivery integrations are not implemented.

Roadmap capabilities:

- OCR for scanned files, images, forms, and mixed document bundles.
- Table extraction from invoices, certificates, reports, and forms.
- Search and question answering across document collections.
- Tenant-aware auth/identity/SSO.
- CSV, Excel, webhook, SFTP, object-store artifact, and downstream-system export delivery.

## Example Workflow

1. An insurance operations team uploads a claim bundle with forms, bills, medical records, photos, and correspondence.
2. NeuroDocOps classifies each document, extracts key fields, and identifies missing evidence.
3. The system generates a checklist for claim completeness and routes low-confidence fields to human reviewers.
4. Reviewers validate disputed fields in a document viewer with citations.
5. Approved data is exported to the claims system and stored with an audit trail.
6. Managers ask, "Which claims are missing medical invoices?" and receive citation-backed answers.

## Architecture Direction

```text
Document Upload
  -> Local PDF Text Extraction when embedded text is available
  -> OCR and Layout Parsing later for scans, images, forms, and tables
  -> Document Classification
  -> Field and Table Extraction
  -> Validation Rules
  -> Vector and Full-Text Indexing
  -> Human Review
  -> Checklist and Workflow Automation
  -> Export and API Integration
  -> Audit and Analytics
```

Implemented technical components:

- Local parsing: digital-PDF text extraction for PDFs with embedded text.
- OCR provider contract: deterministic mock OCR for tests and local fixtures.
- Extraction: deterministic insurance rules with confidence scores and citation-oriented metadata.
- Backend: FastAPI service with workflow, repository, provider, object-store, queue, and RBAC boundaries.
- Frontend: reviewer console for intake, source upload, review tasks, field correction, approval, audit, and JSON export.
- Storage: in-memory defaults with optional Postgres and MinIO.
- Security: development RBAC through `X-Actor` and `X-Role` headers.

Roadmap technical components:

- OCR/layout: Azure Document Intelligence, Google Document AI, AWS Textract, PaddleOCR, Surya, Tesseract, LlamaParse, or ABBYY after fit testing.
- Reasoning/search: LLM structured extraction, vector/full-text search, and question answering.
- Security: real auth, tenant isolation, SSO, token validation, and production identity enforcement.

Provider strategy: NeuroDocOps should be pluggable and tiered. The proof-of-concept should default to free/local providers, then allow better paid services as quality, compliance, or customer requirements increase. OCR, LLM reasoning, storage, database, queueing, auth, intake, search, document rendering, monitoring, secrets, billing, and hosting should all sit behind provider interfaces. See `docs/pluggable-provider-development-plan.md`, `docs/pluggable-provider-test-plan.md`, `docs/ocr-provider-strategy.md`, and `docs/system-flow.md`.

## Provider And Plugin Facility

In NeuroDocOps, the plugin facility means configured adapters behind stable backend contracts. It does not currently mean a public plugin marketplace, customer-uploaded runtime code, or a no-code extension builder.

Implemented today:

- `OCRProvider` and `ExtractionProvider` contracts.
- Deterministic `MockOCRProvider` for local/test processing.
- Local digital-PDF text extraction for source PDFs that already contain embedded text.
- Rule-based insurance extraction provider.
- `PacketRepository` with in-memory and Postgres JSONB-backed implementations.
- `ObjectStore` with in-memory and MinIO implementations.
- `JobQueue` with in-memory and Redis implementations.
- Development RBAC through `X-Actor` and `X-Role` headers.
- `/ready` provider metadata that reports safe provider names, tiers, live flags, and adapter status without exposing secrets.

Roadmap/provider areas:

- OCR/document parsing providers for scanned PDFs, images, forms, tables, handwriting, and mixed bundles, such as open-source OCR, Azure Document Intelligence, AWS Textract, Google Document AI, LlamaParse, or ABBYY.
- Extraction/reasoning providers such as deterministic rules, local/recorded fixtures, or opt-in LLM structured extraction.
- Auth/identity providers such as Keycloak, Auth0, Cognito, or Azure Entra ID.
- Search, intake, telemetry, secrets/config, and export-delivery providers.

Default behavior must remain safe: no paid OCR/model provider is required for local development, unit tests, stack smoke tests, or the first claim packet benchmark. Paid/live providers should only run when explicitly enabled through provider-specific configuration and live-provider flags.

For the detailed plugin/provider plan, see `docs/pluggable-provider-development-plan.md`. For the runtime path across services, see `docs/system-flow.md`.

## Current Implementation

This repository includes the first service-oriented foundation for the insurance claims packet workflow:

- FastAPI API service in `services/api/neurodocops_api/main.py`
- Worker service shell in `services/worker/neurodocops_worker/main.py`
- Reviewer console in `services/web/`
- Packet-first domain models in `packages/domain/neurodocops_domain/`
- Repository-backed workflow service in `packages/workflow/neurodocops_workflow/`
- OCR and extraction provider contracts in `packages/providers/neurodocops_providers/`
- Storage repository contracts plus in-memory and Postgres implementations in `packages/storage/neurodocops_storage/`
- Object storage contracts plus in-memory and MinIO implementations in `packages/storage/neurodocops_storage/`
- Job queue contracts plus in-memory and Redis implementations in `packages/jobs/neurodocops_jobs/`
- Header-driven development RBAC primitives in `packages/security/neurodocops_security/`
- Compatibility imports under `neurodocops/` for existing clients and tests
- Local service infrastructure in `infra/docker-compose.yml`
- Claim packet intake, document classification, field extraction, checklist evaluation, review, export, and audit events
- Tests for the service and API workflow
- Product research, API notes, and architecture notes in `docs/`

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn services.api.neurodocops_api.main:app --reload
```

Run the web service locally:

```bash
cd services/web
npm install
npm run dev
```

Run the service stack locally:

```bash
python scripts/server_switch.py on
python scripts/server_switch.py status
python scripts/server_switch.py logs
python scripts/server_switch.py off
```

Useful local stack options:

```bash
python scripts/server_switch.py on --no-build
python scripts/server_switch.py on --skip-smoke
```

Run tests:

```bash
pytest
```

Local one-process runs still default to an in-memory `PacketRepository`, in-memory object store, in-memory job queue, and deterministic mock OCR/rule-based extraction by design. Set `NEURODOCOPS_STORAGE_BACKEND=postgres` and `DATABASE_URL` to use the durable JSONB-backed Postgres repository. Set `NEURODOCOPS_JOB_QUEUE_BACKEND=redis` and `REDIS_URL` to enqueue packet processing jobs for the worker. Set `NEURODOCOPS_OBJECT_STORAGE_BACKEND=minio` plus the `OBJECT_STORAGE_*` variables to store uploaded source documents in MinIO. Paid OCR/model providers should remain disabled unless explicitly enabled with provider-specific environment variables and live-provider flags. The `/ready` endpoint reports safe provider metadata without exposing credentials, database URLs, Redis URLs, object keys, or storage secrets. The project now has separate deployable API, worker, web, Postgres, Redis, and MinIO service boundaries so persistence, object storage, queue processing, and real OCR can be added without collapsing everything back into one toy process.

## Development RBAC

The current API includes a minimal header-driven RBAC layer for local development and tests. Send `X-Actor` and `X-Role` with API requests:

```bash
curl http://localhost:8000/claim-packets \
  -H 'X-Actor: reviewer@example.com' \
  -H 'X-Role: reviewer'
```

Supported roles are `admin`, `manager`, `reviewer`, `auditor`, and `integration`. Missing headers currently default to `dev-admin` with role `admin` for local compatibility. Real auth, tenant isolation, SSO, and production identity enforcement remain future work.

## Agent Team

Project-local OpenCode agents live under `.opencode/agent/` and coordinate work like a small DevOps/product team:

- `neurodocops-devops-lead`: cross-service coordination and integration.
- `neurodocops-api-rbac-engineer`: API, workflow, provider metadata, RBAC, and backend tests.
- `neurodocops-worker-infra-engineer`: worker, Redis, Postgres, MinIO, Docker Compose, and one-click stack scripts.
- `vigolium-ui-ux-designer`: dark, high-trust, proof-oriented reviewer console direction.
- `neurodocops-qa-release-engineer`: regression checks, build checks, and release validation.
- `neurodocops-docs-product-engineer`: product, architecture, API, RBAC, provider, and local-ops documentation.

Restart OpenCode after changing `.opencode` files so the running session loads the updated agent and skill definitions.

## UI Direction

The reviewer console in `services/web/` now follows a dark, evidence-first, audit-console direction inspired by the seriousness of Vigolium-style security review products. It must not copy Vigolium assets, logos, exact text, screenshots, or proprietary layout. The UI should surface evidence, citations, review exceptions, RBAC context, approval state, and export safety using only backend-supported behavior.

## Data Model Ideas

Core entities may include:

- `Organization`
- `Workspace`
- `Packet`
- `ClaimPacket`
- `Document`
- `DocumentPage`
- `DocumentType`
- `ExtractionSchema`
- `ExtractedField`
- `ChecklistTemplate`
- `ChecklistItem`
- `ValidationRule`
- `ReviewTask`
- `Citation`
- `ExportJob`
- `AuditLog`

## Success Metrics

- Claim packet processing time reduced compared with manual review
- Manual review time per packet
- Packet completeness detection rate
- Missing evidence detection rate
- Field extraction accuracy after human review
- Percentage of documents automatically classified
- Reviewer correction rate per document type
- Export error rate into downstream claims systems
- Time from claim packet receipt to approved workflow output

## Compliance and Safety

NeuroDocOps should be designed for sensitive business documents from the beginning.

Important requirements:

- Access control by organization, workspace, and role
- Encryption for stored files and extracted data
- Audit logs for viewing, editing, exporting, and deleting records
- Human approval before critical exports or compliance decisions
- Data retention and deletion controls
- Clear confidence scores and source references
- Tenant isolation for enterprise customers
- Deployment options for regulated customers where needed

## Roadmap

### Phase 1: Insurance Claims Packet MVP

- Claim packet intake
- Document classification
- Structured field extraction with citations
- Claim completeness checklist
- Human review tasks with resolve/reopen actions, assignment metadata, priority/due dates, and queue filters
- Approval and JSON export
- Audit event stream

### Phase 2: Workflow Automation

- Approval flows
- SLA/escalation automation, notifications, and saved/shared task queues
- API integrations
- Custom extraction templates
- Compliance checklist automation
- Bulk processing and exception handling

### Phase 3: Enterprise Intelligence

- Cross-document analytics
- Compliance dashboards
- Automated missing-document and exception detection
- Integration with ERP, CRM, claims, HR, procurement, and accounting systems
- Reusable vertical packages for fashion, healthcare administration, finance, and logistics

## Strategic Role

NeuroDocOps should be the reusable AI engine behind Neurosformer's vertical products. The same OCR, extraction, RAG, human review, audit logging, checklist, and workflow automation capabilities can power NeuroFashionOps, NeuroClinic Docs, and future regulated-industry products.

## Positioning

NeuroDocOps is an AI document operations platform for regulated workflows. It helps organizations convert document chaos into structured, auditable, searchable, and actionable business operations.

## Status

Concept and MVP planning stage.

## License

Proprietary. Copyright Neurosformer.
