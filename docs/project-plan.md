# NeuroDocOps Project Plan

## Scope

NeuroDocOps should focus on insurance claims packet operations, not generic OCR or PDF chat. The MVP is a reviewer workspace and API that turns a multi-document claim packet into classified documents, extracted fields with citations, completeness checks, review tasks, human approval, export, and audit history.

The market validation and positioning rationale are documented in `docs/market-validation.md`. Treat that document as the source of truth for why this product should stay focused on claims evidence operations instead of becoming a generic AI document dashboard.

## Build Now

1. Enforce the regulated workflow boundary: no export until a packet is approved and review tasks are resolved.
2. Extract real claim fields from the current mock-text pipeline: claim number, policy number, loss date, invoice amount, identity name, provider/service fields where present.
3. Return export data as document-level structured fields with confidence and citations, not only a flattened summary.
4. Add loss-type checklist rules for auto/property and medical/injury packets.
5. Build a pluggable provider system so free/local providers work first and paid providers can be selected by customer quality/compliance needs.
6. Add tests around blocked export, review gating, request-changes behavior, structured fields, loss-type evidence requirements, provider routing, and provider cost controls.

## Provider Strategy

NeuroDocOps should use a tiered provider model: free/local by default, cheap proof-of-concept providers next, paid production providers only when quality or compliance requires them, and enterprise/customer-specific providers for regulated deployments.

Provider areas include OCR/document parsing, LLM reasoning, object storage, database, queueing, auth, intake, search, document rendering, telemetry, secrets, billing, and hosting. The detailed development plan is in `docs/pluggable-provider-development-plan.md`; the test strategy is in `docs/pluggable-provider-test-plan.md`; OCR-specific strategy is in `docs/ocr-provider-strategy.md`.

Before any provider becomes a default route, it must pass an agentic fit-test workflow: research the provider, run it against benchmark claim packet documents or recorded fixtures, normalize the output, score quality/cost/latency/compliance/reviewer value, and then decide whether it is rejected, experimental, cheap-tier, balanced-tier, premium-tier, enterprise-only, or document-type-specific.

## Frontend Direction

The attached scaffold is stored as `vagescaffolds/NeuroDocopsanything.zip`. It contains a large generated web/mobile project with useful NeuroDocOps-looking screens, but it also includes unrelated mock API routes, auth, upload, provider settings, and field-correction assumptions that the current FastAPI backend does not support yet.

Use it as visual/product inspiration, not as the source of truth. The repo now includes a lean `services/web/` reviewer console wired to the current FastAPI endpoints. The current product direction is a dark, high-trust, proof/evidence console inspired by serious security-audit tooling. Do not copy Vigolium assets, logos, exact text, screenshots, or proprietary layout.

If expanding the frontend, keep these screens:

1. Packet dashboard with status, document count, checklist failures, and open review tasks.
2. New packet intake screen using text-based document input until multipart upload exists.
3. Packet workspace with workflow stepper, document list, extracted fields, checklist, review tasks, and audit summary.
4. Review queue synthesized from packet review tasks until a dedicated review-task API exists.
5. Audit timeline for packet events.
6. Export preview that copies/downloads JSON and disables export until backend approval rules pass.

The first-surface operating model is documented in `docs/first-surface-operating-model.md`. Use it as the source of truth for user roles, real tasks, plugin boundaries, first document sources, and the next real product slice.

## Defer

1. Generic document chat.
2. Autonomous claim approval, denial, payment, or fraud scoring.
3. Full Guidewire/Duck Creek integrations.
4. Multi-OCR marketplace.
5. Advanced analytics dashboards.
6. Complex no-code extraction template builder.

## Next Milestones

### Milestone 1: Demoable Workflow

- Approval-gated export.
- Structured rule-based extraction.
- Loss-type checklist.
- Structured export payload.
- Sample packet payloads and tests.

### Milestone 2: Reviewer Product

- Field correction endpoint and reviewer UI are implemented for extracted fields.
- Correction audit events are implemented for corrected field values.
- Task-level review resolution endpoints remain.
- Frontend review console exists; continue making it source-document and audit-proof oriented.

### Milestone 3: Pilot Backend

- Postgres persistence.
- Redis-backed worker jobs for packet processing.
- Object storage adapter.
- Pluggable OCR/document parser router with mock/local providers first and Azure/LlamaParse/AWS/Google benchmark adapters later.
- Background jobs for OCR/extraction/export retries.
- Organization/workspace/user fields.
- Basic auth and roles. A development header-RBAC foundation now exists through `X-Actor` and `X-Role`; remaining work is tenant isolation, real identity provider/SSO, and production-grade auth enforcement.

## Agent Team

Project-local OpenCode agents define the intended working team:

- DevOps Lead for cross-service coordination and integration.
- API/RBAC Engineer for FastAPI, workflow contracts, provider metadata, RBAC, and backend tests.
- Worker/Infrastructure Engineer for Redis jobs, Postgres/MinIO storage, Docker Compose, and one-click stack scripts.
- Vigolium UI/UX Designer for the dark proof-oriented reviewer console.
- QA/Release Engineer for regression checks, frontend builds, Compose validation, and release notes.
- Docs/Product Engineer for product, architecture, API, RBAC, provider, and local-ops documentation.
- Research Agent for provider research, public/synthetic benchmark documents, workflow evidence, compliance constraints, and integration options before implementation.

### Milestone 3.5: Provider Proof Of Concept

- Provider configuration registry.
- Provider evaluation harness and scorecard.
- OCR cache keyed by source document checksum and provider config.
- Local PDF text extraction provider.
- Paid OCR live flag and cost telemetry.
- Source document preview/download.
- Field correction endpoint and correction audit.
- Postgres full-text search provider before paid search.

### Milestone 4: Pilot Readiness

- Tenant isolation enforcement.
- Retention/deletion policy support.
- Export schema versioning.
- CSV export and webhook export.
- Operational metrics for packet cycle time, review load, missing evidence, and correction rate.
