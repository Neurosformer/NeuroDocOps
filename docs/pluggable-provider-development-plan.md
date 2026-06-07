# Pluggable Provider Development Plan

Date: 2026-06-06

## Goal

Build NeuroDocOps as a real proof-of-concept system, not a toy, while keeping operating costs low.

The product should support this rule:

> Free or cheap providers by default. Better paid providers can be plugged in when the customer, quality target, compliance requirement, or document complexity justifies the cost.

This means every expensive dependency must sit behind an interface. The workflow should not care whether OCR comes from mock OCR, PaddleOCR, Azure, AWS, Google, LlamaParse, or ABBYY. The same rule applies to storage, queueing, auth, search, monitoring, secrets, intake, and hosting.

## Provider Tier Model

Every provider area should support at least three tiers.

| Tier | Meaning | Example |
| --- | --- | --- |
| Tier 0 | Local/free/test provider | Mock OCR, local Postgres, local Redis, MinIO, `.env` |
| Tier 1 | Cheap proof-of-concept provider | Local PDF text extraction, open-source OCR, self-hosted Keycloak, Postgres full-text |
| Tier 2 | Paid production provider | Azure Document Intelligence, S3, Auth0, Sentry, OpenSearch |
| Tier 3 | Enterprise/customer-specific provider | ABBYY, customer VPC storage, Azure Entra ID, customer-managed cloud |

The first implementation should always start at Tier 0/Tier 1, then route upward only when needed.

## Provider Areas

| Area | Interface To Build | Tier 0 / Low-Cost | Paid / Better Providers | POC Priority |
| --- | --- | --- | --- | --- |
| OCR / document parsing | `OCRProvider`, `DocumentParserProvider`, `ProviderRouter` | Mock OCR, PDF text extraction, PaddleOCR/Surya experiments | Azure DI, Google Document AI, AWS Textract, LlamaParse, ABBYY | High |
| LLM / structured reasoning | `ReasoningProvider`, `StructuredExtractionProvider` | Off, deterministic rules | GPT, Claude, Gemini, Azure OpenAI | Medium |
| Object storage | `ObjectStore` | In-memory, MinIO | S3, Azure Blob, GCS, customer bucket | Done foundation |
| Database | `PacketRepository` plus future normalized repos | In-memory, local Postgres | Managed Postgres/RDS/Azure PostgreSQL/Cloud SQL | Done foundation |
| Queue / background jobs | `JobQueue` | In-memory, local Redis | Managed Redis, SQS, Cloud Tasks, Celery/Dramatiq | Done foundation |
| Auth / identity | `IdentityProvider`, `PermissionProvider` | Dev actor header, mock users | Auth0, Clerk, Keycloak, Cognito, Azure Entra ID | High |
| Email/file intake | `IntakeProvider` | Manual upload/API | SendGrid, Mailgun, Graph API, Gmail API, SFTP | Medium |
| Search/indexing | `SearchProvider` | Postgres full-text | OpenSearch, Elasticsearch, Meilisearch, vector DB | Medium |
| Document viewer/rendering | `DocumentRenderProvider` | Browser PDF viewer, PDF.js | PSPDFKit, cloud rendering, page image rendering | High |
| Monitoring/logging | `TelemetryProvider` | Local logs | Sentry, Datadog, OpenTelemetry, Grafana | Medium |
| Secrets/config | `SecretProvider` | `.env` | Doppler, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager | Medium |
| Payments/billing | `BillingProvider` | None/manual invoice | Stripe | Low |
| Deployment/hosting | deployment adapter/runbook | Docker Compose | Fly.io, Render, Railway, AWS, Azure, GCP, customer VPC | Medium |

## Design Principles

1. No paid provider should be required for unit tests.
2. No paid provider should be required for local development.
3. Every live paid provider should be opt-in via environment variables.
4. Every paid provider call should be logged with provider, model/version, page count, and estimated cost.
5. OCR/document parsing results should be cached by file checksum and provider config.
6. Provider selection should happen in the worker or provider router, not inside API routes.
7. The API should expose provider-neutral workflow objects.
8. Customers should be able to choose cheap, balanced, or premium provider modes.
9. Provider failure should degrade to human review, not silently corrupt extracted data.
10. The default POC should be useful with local services only.
11. No provider becomes a default provider until it passes a fitting test against NeuroDocOps documents.
12. Provider decisions should be scorecard-driven, not brand-driven.

## Agentic Provider Evaluation Strategy

Before plugging a provider into the production path, run an agentic evaluation cycle. The purpose is to prevent blind integration work and to choose providers by fit, cost, quality, and customer constraints.

Agent roles:

| Agent | Responsibility | Output |
| --- | --- | --- |
| Provider Research Agent | Research pricing, features, compliance, limits, deployment model, and support posture | Provider research brief |
| Technical Fit Agent | Checks API/SDK shape, artifact quality, citation support, latency, failure modes, and integration effort | Technical fit report |
| Cost Agent | Estimates cost per page, packet, month, and pilot volume; identifies hidden costs | Cost model |
| Quality Benchmark Agent | Runs provider against benchmark packet set and compares outputs with expected fields/citations | Quality scorecard |
| Compliance/Risk Agent | Checks PHI/PII posture, data retention, model-training policy, SOC2/HIPAA/BAA/customer-cloud fit | Risk scorecard |
| Product Fit Agent | Decides whether provider improves reviewer workflow and reduces human correction time | Workflow-fit verdict |
| Research Agent | Finds public/synthetic benchmark documents, provider facts, workflow evidence, compliance notes, and integration constraints before implementation | Research brief and document-source notes |

The final decision should be a provider scorecard and recommendation:

```text
reject
keep as experimental
use as cheap-tier provider
use as balanced-tier provider
use as premium provider
use only for specific document types
use only for specific customer cloud/compliance requirements
```

## Provider Scorecard

Each provider gets scored before integration.

| Score Area | What It Measures |
| --- | --- |
| OCR accuracy | Reads text correctly on real claim packet pages |
| Layout quality | Preserves pages, sections, tables, checkboxes, signatures, and reading order |
| Field accuracy | Extracts target fields such as claim number, policy number, dates, totals, provider, invoice fields |
| Citation quality | Produces source page/snippet/region that a reviewer can verify |
| Table quality | Handles invoices, medical bills, EOBs, and row/column structure |
| Latency | Time per page and per packet |
| Reliability | Timeout rate, retry behavior, empty-result rate, malformed output rate |
| Cost | Cost per page, per packet, and per accepted reviewed packet |
| Compliance | SOC2/HIPAA/BAA/private cloud/data-retention/model-training fit |
| Integration effort | SDK/API complexity, artifact normalization effort, maintenance burden |
| Reviewer value | Reduction in human correction time and increase in reviewer trust |

Decision rule:

> The best provider is not always the most accurate provider. The best provider is the provider with the best quality/cost/compliance fit for a specific document workflow.

## Provider Fitting Workflow

Use this process before adding any serious provider integration:

```text
candidate provider
  -> research by agent
  -> build minimal adapter or fixture runner
  -> run benchmark packet set
  -> normalize provider output into NeuroDocOps artifacts
  -> score quality/cost/latency/compliance/reviewer value
  -> decide tier and supported document types
  -> only then productionize adapter
```

This prevents wasting engineering time on providers that are famous but not actually useful for our target packet workflow.

## Document Research And Benchmark Sources

Provider evaluation must use documented benchmark packet sources. The Research Agent owns the first pass and must label every source as public, synthetic, de-identified, licensed, or confidential. The first version should prefer public/synthetic documents and text fixtures before adding live paid OCR.

Initial benchmark categories:

- Auto claim packet: claim form, incident report, repair estimate/invoice, identity placeholder.
- Property claim packet: proof of loss, contractor estimate, policy declaration sample, photos metadata.
- Medical/injury packet: medical bill, EOB-style statement, treatment note, identity placeholder.
- Workers compensation/disability packet: first report of injury, employer statement, medical note, wage statement.

Each benchmark packet should include a manifest with expected document classes, expected extracted fields, required evidence, known missing evidence, and expected review tasks. See `docs/first-surface-operating-model.md` for the operating model and immediate first real slice.

## Target Architecture

```text
services/web
  -> services/api
      -> packages/workflow
      -> packages/providers
          -> provider router
          -> OCR/document parser providers
          -> extraction/reasoning providers
      -> packages/storage
          -> packet repository
          -> object store
      -> packages/jobs
          -> job queue
      -> packages/security
          -> identity and permission providers
      -> packages/search
          -> search/index providers
      -> packages/telemetry
          -> logging/metrics/error providers
  -> services/worker
      -> consumes jobs
      -> loads documents from object store
      -> routes provider calls by tier/config/confidence
      -> persists OCR/extraction/review artifacts
```

## Module-By-Module Development Plan

### Module 1: Provider Configuration Registry

Purpose: centralize provider choice and tier settings.

Build:

- `packages/config` or `packages/providers/.../settings.py`.
- Environment-driven provider settings.
- `ProviderTier`: `free`, `cheap`, `balanced`, `premium`, `enterprise`.
- Cost budget settings: max pages per run, max live OCR calls, live provider enable flag.

Acceptance criteria:

- App boots with no paid credentials.
- App reports active providers in `/ready` or admin/debug endpoint.
- Unknown provider names fail clearly.

### Module 2: Provider Evaluation Harness

Purpose: crosscheck providers before plugging them into the system.

Build:

- Provider benchmark runner.
- Benchmark dataset manifest.
- Expected field/citation ground-truth format.
- Provider output normalizer.
- Provider scorecard output.
- Cost estimator per provider call.
- Recommendation report generator.

Acceptance criteria:

- Can compare at least mock/local extraction against one candidate provider or recorded fixture.
- Produces provider scorecard with quality, cost, latency, and compliance fields.
- Does not require live paid provider calls by default.
- Rejects provider as default if benchmark score is below threshold.

### Module 3: OCR Provider Router And Cache

Purpose: avoid sending every page to expensive OCR.

Build:

- `OCRProvider` extensions for provider metadata and artifacts.
- `OCRCacheRepository` keyed by file checksum, page hash, provider name, provider version, and options.
- `ProviderRouter` that chooses local/free/cloud path.
- Local PDF text extraction provider.
- Keep mock OCR as Tier 0.

Routing logic:

```text
if OCR cache hit: return cached artifact
if digital PDF text is usable: use local text extraction
if provider tier is free/cheap: use open-source OCR candidate
if document is hard or low-confidence: escalate to cloud provider
if cloud is disabled: create review task instead of paid call
```

Acceptance criteria:

- Same uploaded document is not OCR-billed twice.
- Worker can process uploaded source files without requiring manual text in the long term.
- Paid OCR cannot run unless explicitly enabled.

### Module 4: Document Rendering And Citation Artifacts

Purpose: make citations inspectable, not just text snippets.

Build:

- Source document download endpoint.
- PDF/image preview endpoint or direct object-store signed/download path.
- Page-level OCR artifact model.
- Citation fields: document id, page, snippet, optional bounding box, provider artifact id.
- Frontend document viewer using PDF.js/browser PDF first.

Acceptance criteria:

- Reviewer can open original source document.
- Reviewer can see extracted field and source page/snippet.
- No premium viewer dependency required for POC.

### Module 5: Field Correction And Review Workflow

Purpose: convert OCR/extraction from demo output into reviewable work.

Build:

- Field correction endpoint.
- Task-level review endpoints.
- Correction audit events with previous/new values.
- Verified field status.
- Frontend correction UI.

Acceptance criteria:

- Reviewer can correct extracted values.
- Corrections persist and appear in export.
- Audit shows who changed what and when.

### Module 6: Auth And Tenant Provider

Purpose: make the POC credible for sensitive documents.

Build:

- `IdentityProvider` interface.
- Dev provider using headers or seeded users.
- `organization_id`, `workspace_id`, `actor_id` propagation.
- Basic role checks: admin, manager, reviewer, auditor.
- Future adapters: Keycloak, Auth0, Cognito, Entra ID.

Acceptance criteria:

- Local dev works with mock identity.
- API does not expose all packets across tenants once tenant fields are enabled.
- Audit events use actor identity from provider.

### Module 7: Search Provider

Purpose: search packets without paying for search infrastructure immediately.

Build:

- `SearchProvider` interface.
- Postgres full-text provider first.
- Index packet metadata, filenames, OCR text, extracted fields, checklist/review reasons.
- Future adapters: OpenSearch/Elasticsearch/Meilisearch/vector DB.

Acceptance criteria:

- Search works locally with Postgres only.
- Expensive/vector search is not required for POC.

### Module 8: Intake Providers

Purpose: expand beyond manual upload after the core loop works.

Build:

- `IntakeProvider` interface.
- Manual upload/API provider remains default.
- Later: email inbox, Graph API, Gmail API, SFTP, webhook intake.

Acceptance criteria:

- Intake sources create the same provider-neutral claim packet records.
- No intake provider should bypass audit.

### Module 9: Telemetry And Cost Tracking

Purpose: know provider usage and failures before costs surprise us.

Build:

- `TelemetryProvider` interface.
- Local structured logs default.
- Provider call events: provider, operation, pages, latency, status, estimated cost.
- Optional Sentry/OpenTelemetry adapter.

Acceptance criteria:

- Every paid provider call is visible.
- Failed provider calls create job errors or review tasks.
- POC can report cost per packet.

### Module 10: Export Providers

Purpose: export is where customer value appears.

Build:

- JSON export remains default.
- CSV export provider.
- Export artifact storage in object store.
- Future webhook/API export provider.

Acceptance criteria:

- Approved corrected fields export consistently.
- Export has schema version and audit event.

### Module 11: Deployment Modes

Purpose: make the same system runnable cheaply or professionally.

Build modes:

- `local`: Docker Compose, mock/local providers.
- `poc`: Docker Compose or cheap VM, local/minimal paid providers.
- `pilot`: managed Postgres/storage, selected OCR provider, auth provider.
- `enterprise`: customer VPC/cloud, enterprise auth, customer-approved OCR/storage.

Acceptance criteria:

- Environment file selects mode.
- Provider failures are explicit.
- No hidden required paid service.

## POC Build Order

Build in this order:

1. Provider configuration registry.
2. Provider evaluation harness and scorecard.
3. OCR router/cache with mock + local PDF text extraction.
4. Source document preview/download and citation artifacts.
5. Field correction and task-level review.
6. Dev auth/tenant provider.
7. Postgres full-text search provider.
8. Cost/telemetry tracking.
9. Optional live OCR benchmark adapters.

This order proves the useful customer loop before adding expensive integrations.

## What Not To Build Yet

Do not build these until the POC loop is proven:

- Multi-provider marketplace UI.
- Deep Guidewire/Duck Creek connector.
- Complex no-code workflow builder.
- Autonomous claim decisioning.
- Fraud scoring.
- Large analytics suite.
- Paid LLM extraction everywhere.
- Enterprise SSO before basic tenant/auth shape.

## POC Definition: Not A Toy

The proof-of-concept is not customer-production-ready, but it must be real enough to validate the business.

It must support:

1. Real source document upload.
2. Source document storage.
3. At least one no-cost or low-cost OCR/parser route.
4. Provider-neutral OCR artifact storage.
5. Extracted fields with citations.
6. Reviewer correction.
7. Checklist/review tasks.
8. Human approval gate.
9. JSON/CSV export.
10. Audit trail with actor.
11. Cost visibility per packet.

If the POC cannot show this loop, more provider integrations will not matter.
