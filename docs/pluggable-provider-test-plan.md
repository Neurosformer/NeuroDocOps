# Pluggable Provider Test Plan

Date: 2026-06-06

## Goal

Validate that NeuroDocOps can swap providers by cost/quality tier without breaking the workflow.

The test strategy must prove:

1. Free/local providers work by default.
2. Paid providers are opt-in.
3. Provider outputs round-trip through storage and export.
4. Failed providers degrade to review/errors, not silent bad data.
5. The same workflow works regardless of provider choice.
6. No provider becomes default unless it passes a fit test and scorecard gate.

## Test Layers

### Unit Tests

Run by default with no paid credentials.

Coverage:

- Provider config parsing.
- Unknown provider rejection.
- Default providers are free/local.
- OCR cache key generation.
- Provider routing decisions.
- Object store contract.
- Repository contract.
- Job queue contract.
- Auth mock provider.
- Search provider basics.

Command:

```bash
.venv/bin/pytest -q
```

### Contract Tests

Every provider type gets a contract test.

| Provider Area | Contract Must Prove |
| --- | --- |
| OCR/parser | Returns text/pages/provider metadata and stable citations |
| Object store | Stores and retrieves bytes; preserves checksum and metadata |
| Repository | Persists packet, documents, fields, audit, jobs/artifacts |
| Queue | Enqueue/dequeue/status update/failure behavior |
| Auth | Resolves actor/org/workspace/roles |
| Search | Indexes and searches provider-neutral records |
| Telemetry | Records provider calls and errors |

Contracts should run against in-memory/local providers by default and against paid providers only when credentials are set.

### Integration Tests

Integration tests are opt-in.

Examples:

```bash
NEURODOCOPS_TEST_DATABASE_URL=postgresql://... .venv/bin/pytest tests/test_storage_repository_contract.py
NEURODOCOPS_LIVE_OCR_ENABLED=true NEURODOCOPS_OCR_PROVIDER=azure .venv/bin/pytest tests/integration/test_azure_ocr.py
```

Rules:

- Skip if credentials are missing.
- Never run paid tests in default CI/local mode.
- Use tiny sample documents.
- Cache responses where possible.
- Print estimated provider cost.

### End-To-End Tests

Use the orchestrator for local stack validation.

Command:

```bash
.venv/bin/python scripts/orchestrate_stack.py
```

Expected:

- API healthy.
- API ready.
- Web healthy.
- MinIO healthy.
- Worker processes a queued packet job.
- Packet reaches review state.
- Review approval succeeds.
- Export succeeds.
- Audit contains expected actions.

### Benchmark Tests

Benchmarks are not pass/fail unit tests. They compare provider quality and cost.

Benchmark set:

- 20-50 full claim packets or 100-300 representative pages.
- Clean PDFs.
- Bad scans.
- Claim forms.
- Incident reports.
- Repair invoices.
- Medical bills.
- Identity evidence.
- Insurance cards.
- Mixed packets.

Metrics:

- OCR word accuracy.
- Document classification accuracy.
- Field precision/recall.
- Table row/column accuracy.
- Citation correctness.
- Latency.
- Cost per page.
- Cost per accepted packet.
- Human correction time.
- Reviewer trust score.

### Agentic Fit Tests

Agentic fit tests are provider decision workflows. They combine research, benchmark outputs, cost analysis, and product-fit review before a provider is adopted.

Required fit-test artifacts:

- Provider research brief.
- Provider config and credential requirements.
- Benchmark result JSON.
- Cost estimate.
- Compliance/risk notes.
- Normalized artifact comparison.
- Final scorecard.
- Recommendation: reject, experimental, cheap tier, balanced tier, premium tier, enterprise-only, or document-type-specific.

Fit-test pass criteria:

- Provider output can be normalized into NeuroDocOps artifacts.
- Provider does not require paid calls for default tests.
- Provider produces usable citations or its citation limitations are explicitly documented.
- Provider cost can be estimated per page and per packet.
- Provider failure behavior is tested.
- Provider improves at least one target workflow metric: accuracy, citation quality, table quality, latency, compliance fit, or reviewer correction time.

Provider default gate:

> A provider cannot become a default route until the scorecard shows it beats the current route on real target documents by enough quality, cost, compliance, or reviewer-time value to justify integration and operating cost.

## Provider-Specific Test Matrix

| Provider | Default Test Mode | Live Test Mode | Required Before Production? |
| --- | --- | --- | --- |
| Mock OCR | Always | N/A | Yes |
| Local PDF text extraction | Always | N/A | Yes |
| PaddleOCR/Surya | Optional local | N/A | Benchmark before use |
| LlamaParse | Fixture/recorded | Opt-in live | Benchmark before pilot |
| Azure DI | Fixture/recorded | Opt-in live | Benchmark before pilot |
| AWS Textract | Fixture/recorded | Opt-in live | Optional fallback |
| Google Document AI | Fixture/recorded | Opt-in live | Optional fallback |
| ABBYY | Contract placeholder | Customer-driven | Enterprise fallback only |
| MinIO | Local compose | N/A | Yes |
| S3/Azure Blob/GCS | Mock/contract | Opt-in live | Customer/pilot dependent |
| In-memory queue | Always | N/A | Yes |
| Redis queue | Local compose | Managed Redis opt-in | Yes |
| Dev auth | Always | N/A | Yes |
| Auth0/Keycloak/Cognito/Entra | Mock/contract | Opt-in live | Pilot dependent |

## Cost-Safety Tests

Add tests that enforce cost controls:

1. Paid OCR provider raises unless `NEURODOCOPS_LIVE_OCR_ENABLED=true`.
2. Live provider tests skip unless credentials are present.
3. OCR cache returns cached result on duplicate file hash.
4. Router uses local provider when PDF text extraction is sufficient.
5. Router escalates only when confidence is below threshold or document type requires layout/table extraction.
6. Provider call telemetry records estimated cost.
7. Provider scorecard includes estimated cost per accepted packet.
8. Provider fitting test fails if estimated live cost exceeds configured POC budget without explicit override.

## Failure Tests

Provider failure is normal. Tests should prove safe degradation.

Scenarios:

- OCR provider timeout.
- OCR provider credential missing.
- OCR provider returns empty text.
- Object store unavailable.
- Queue unavailable.
- Database unavailable.
- Search provider unavailable.
- Auth provider unavailable.

Expected behavior:

- No silent success.
- Job becomes failed or packet gets review task.
- Audit/telemetry records failure.
- API returns clear error for control-plane failures.

## Module Acceptance Tests

### Provider Configuration Registry

- Defaults to free/local providers.
- Rejects unknown providers.
- Paid providers require live flag.
- `/ready` or debug endpoint reports configured provider names.

### Provider Evaluation Harness

- Benchmark runner accepts provider name and dataset manifest.
- Runner can use recorded fixtures instead of live paid calls.
- Scorecard includes quality, cost, latency, compliance, integration effort, and reviewer-value dimensions.
- Provider recommendation is deterministic from score thresholds.

### OCR Router And Cache

- Same file is not processed twice.
- Local text extraction wins for digital PDFs.
- Cloud provider is not called unless enabled.
- Low-confidence result creates review task or escalation.

### Document Rendering And Citations

- Uploaded source document can be downloaded/previewed.
- Extracted field links to document/page/snippet.
- Missing citation fails validation for required fields.

### Field Correction

- Reviewer can update field.
- Export uses corrected value.
- Audit stores old/new value.

### Auth/Tenant

- Packet list is tenant-scoped.
- Reviewer cannot export without permission.
- Audit actor comes from identity provider.

### Search

- Search finds packet by claim reference, claimant, filename, extracted field, and OCR text.
- Search does not return another tenant's packet.

### Telemetry/Cost

- Provider call is logged.
- Cost estimate is stored.
- Cost per packet can be computed.

## Regression Suite

Before each milestone handoff, run:

```bash
.venv/bin/pytest -q
cd services/web && npm run build
.venv/bin/python scripts/orchestrate_stack.py --no-build
```

If provider code changed, also run relevant contract tests.

If frontend workflow changed, run the orchestrator smoke test and manually inspect the web console.

## Definition Of Done For A Provider Module

A provider module is done when:

1. It has an interface/protocol.
2. It has at least one free/local implementation.
3. It has a factory driven by environment variables.
4. It has contract tests.
5. It does not require paid credentials by default.
6. It records provider metadata.
7. It handles failure explicitly.
8. It is documented in `.env.example` and architecture docs.
9. It has a completed provider fit scorecard before becoming a default or production route.
