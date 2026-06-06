# NeuroDocOps Project Plan

## Scope

NeuroDocOps should focus on insurance claims packet operations, not generic OCR or PDF chat. The MVP is a reviewer workspace and API that turns a multi-document claim packet into classified documents, extracted fields with citations, completeness checks, review tasks, human approval, export, and audit history.

## Build Now

1. Enforce the regulated workflow boundary: no export until a packet is approved and review tasks are resolved.
2. Extract real claim fields from the current mock-text pipeline: claim number, policy number, loss date, invoice amount, identity name, provider/service fields where present.
3. Return export data as document-level structured fields with confidence and citations, not only a flattened summary.
4. Add loss-type checklist rules for auto/property and medical/injury packets.
5. Keep the provider interfaces so Azure Document Intelligence or another OCR adapter can replace the mock provider later.
6. Add tests around blocked export, review gating, request-changes behavior, structured fields, and loss-type evidence requirements.

## Frontend Direction

The attached scaffold is stored as `vagescaffolds/NeuroDocopsanything.zip`. It contains a large generated web/mobile project with useful NeuroDocOps-looking screens, but it also includes unrelated mock API routes, auth, upload, provider settings, and field-correction assumptions that the current FastAPI backend does not support yet.

Use it as visual/product inspiration, not as the source of truth. The repo now includes a lean `frontend/` reviewer console wired to the current FastAPI endpoints.

If expanding the frontend, keep these screens:

1. Packet dashboard with status, document count, checklist failures, and open review tasks.
2. New packet intake screen using text-based document input until multipart upload exists.
3. Packet workspace with workflow stepper, document list, extracted fields, checklist, review tasks, and audit summary.
4. Review queue synthesized from packet review tasks until a dedicated review-task API exists.
5. Audit timeline for packet events.
6. Export preview that copies/downloads JSON and disables export until backend approval rules pass.

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

- Field correction endpoint.
- Task-level review endpoints.
- Better audit events for corrections and failed/blocked operations.
- Frontend review console.

### Milestone 3: Pilot Backend

- Postgres persistence.
- Object storage adapter.
- Real OCR adapter, preferably Azure Document Intelligence first.
- Background jobs for OCR/extraction.
- Organization/workspace/user fields.
- Basic auth and roles.

### Milestone 4: Pilot Readiness

- Tenant isolation enforcement.
- Retention/deletion policy support.
- Export schema versioning.
- CSV export and webhook export.
- Operational metrics for packet cycle time, review load, missing evidence, and correction rate.
