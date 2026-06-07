# NeuroDocOps Agent Team Handoff

Date: 2026-06-08

This handoff is for the next NeuroDocOps agent team. It captures the current completed work, the product direction, the hard constraints, and the next batches to start from. Use this document before opening new implementation work.

## Current Repository State

Latest pushed commit:

```text
f463dd1 Add PDF processing and reviewer queue ownership
```

Branch state after the push was clean:

```text
main...origin/main
```

Recent completed commits:

```text
f463dd1 Add PDF processing and reviewer queue ownership
ac05bc1 Add market validation documentation
57b2a02 Build claims packet operations platform
```

## Product Goal

NeuroDocOps is an insurance claims packet evidence-operations system. It is not a generic document dashboard, not autonomous claim adjudication, and not a consumer portal.

The first useful workflow is:

```text
claim packet intake
  -> source document upload
  -> local/free document parsing when possible
  -> classification and extraction
  -> checklist review tasks
  -> reviewer correction and task resolution
  -> manager/admin approval
  -> approval-gated export
  -> audit proof
```

## Hard Constraints

- Do not enable paid OCR, paid model calls, or live OCR/model providers by default.
- Do not bypass human approval before export.
- Do not collapse the service architecture back into a toy single process.
- Do not claim UI functionality that is not backed by API/workflow behavior.
- Do not copy Vigolium assets, logos, screenshots, exact text, or proprietary layout.
- Keep local/free providers as the default for tests, local stack, and benchmark work.
- Treat `X-Actor` / `X-Role` as development RBAC only, not production auth.
- Use rigorous unit/API/build/config verification. If the user prohibits smoke testing, do not run stack smoke/restart flows.

## Agent Team Roles

Use the project-local OpenCode team:

| Agent | Primary Ownership |
| --- | --- |
| `neurodocops-devops-lead` | Coordinates scope, handoffs, verification, and cross-service consistency |
| `neurodocops-api-rbac-engineer` | API routes, workflow contracts, provider metadata, RBAC, backend tests |
| `neurodocops-worker-infra-engineer` | Worker, queue, object store, Docker Compose, MinIO, Redis, Postgres |
| `vigolium-ui-ux-designer` | Web reviewer console UI/UX, proof-oriented dark workstation |
| `neurodocops-qa-release-engineer` | Regression strategy, test coverage, release gates |
| `neurodocops-docs-product-engineer` | README/docs/product/architecture/API documentation |
| `neurodocops-research-agent` | Public/synthetic document sources, provider research, market/workflow research |

OpenCode must be restarted after agent/skill changes, but the current project agent files are already committed and pushed.

## Completed Batch: Platform Foundation

The earlier platform work created the service-oriented structure:

- `services/api`
- `services/worker`
- `services/web`
- `packages/domain`
- `packages/workflow`
- `packages/providers`
- `packages/storage`
- `packages/jobs`
- `packages/security`
- `infra/docker-compose.yml`
- `scripts/server_switch.py`
- `scripts/orchestrate_stack.py`

The system now has FastAPI, worker/job queue, React web console, Postgres repository option, Redis queue option, MinIO object store option, dev RBAC, provider registry, safe provider metadata, benchmark fixtures, and documentation.

## Completed Batch: Real Source Upload And Local PDF Processing

Implemented in latest commit `f463dd1`.

Key behavior:

- Web intake creates a packet shell and uploads real source files through multipart API.
- API stores source bytes through the configured `ObjectStore`.
- Documents can be downloaded/previewed through the source endpoint.
- `LocalPDFTextOCRProvider` parses embedded text from digital PDFs using local/free code.
- API and worker now inject source-byte loaders so processing can read source bytes from object storage.
- `NEURODOCOPS_OCR_PROVIDER=local_pdf_text` is set in Compose for API and worker.
- Live/paid OCR remains disabled.
- Scanned PDFs, images, handwriting, layout/table extraction, and region-level citations remain roadmap.

Important files:

- `packages/providers/neurodocops_providers/insurance.py`
- `packages/providers/neurodocops_providers/registry.py`
- `packages/workflow/neurodocops_workflow/service.py`
- `services/api/neurodocops_api/main.py`
- `services/worker/neurodocops_worker/main.py`
- `services/web/src/main.jsx`
- `infra/docker-compose.yml`
- `tests/test_provider_registry.py`
- `tests/test_source_document_upload_api.py`
- `tests/test_workflow_service.py`

## Completed Batch: Reviewer Queue Ownership

Implemented in latest commit `f463dd1`.

Key behavior:

- Review tasks now carry queue metadata:
  - `assignee`
  - `priority`: `low`, `normal`, `high`, `urgent`
  - `due_at`
- New queue item model: `ReviewTaskQueueItem`.
- New update body: `ReviewTaskUpdateRequest`.
- New audit events:
  - `review_task_assigned`
  - `review_task_updated`
- New RBAC permissions:
  - `review_task:read`
  - `review_task:update`
- Role behavior:
  - `admin`, `manager`, `reviewer`: read/update queue metadata
  - `auditor`: read-only queue
  - `integration`: no human review queue access
- New API endpoint:
  - `GET /review-tasks`
  - `PATCH /claim-packets/{packet_id}/review-tasks/{task_id}`
- New web route:
  - `/#/review`

Important files:

- `packages/domain/neurodocops_domain/models.py`
- `packages/security/neurodocops_security/rbac.py`
- `packages/workflow/neurodocops_workflow/service.py`
- `services/api/neurodocops_api/main.py`
- `services/web/src/main.jsx`
- `services/web/src/styles.css`
- `tests/test_api.py`
- `tests/test_workflow_service.py`

## Completed Batch: Provider/Plugin Visibility

Implemented behavior:

- Provider/plugin facility is documented as configured backend adapters, not a marketplace or untrusted runtime plugin loader.
- Admin has `/plugins` page showing read-only provider configuration metadata.
- API endpoint exposes safe provider config metadata without secrets:
  - `GET /system/provider-configuration`
- Provider slots documented:
  - OCR/document parsing
  - extraction/reasoning
  - object storage
  - database
  - queue/jobs
  - auth/identity
  - search
  - intake
  - telemetry
  - secrets/config
  - export delivery

Important files:

- `docs/pluggable-provider-development-plan.md`
- `docs/system-flow.md`
- `docs/api.md`
- `docs/mvp-architecture.md`
- `services/web/src/main.jsx`
- `packages/providers/neurodocops_providers/registry.py`

## Latest Verification

Before commit `f463dd1`, the following non-smoke checks passed:

```text
.venv/bin/pytest -q tests/test_workflow_service.py tests/test_api.py
35 passed

.venv/bin/pytest -q
79 passed, 1 skipped

npm run build
passed

docker compose -f infra/docker-compose.yml config
passed
```

Smoke testing and stack restart were not run in the last batches because the user explicitly prohibited smoke testing.

## Current Product Gaps

The next team should not rework already-completed queue/upload/provider foundation. Start from these real gaps:

1. Source document viewer is still basic.
   - Source bytes can be opened/downloaded.
   - There is no page-level PDF viewer, OCR artifact view, table view, or region-level citation display.

2. Local PDF extraction is not scanned OCR.
   - It handles embedded text only.
   - Image-only PDFs, forms, handwriting, checkboxes, signatures, and tables need future OCR/layout providers.

3. Review queue has ownership metadata but no SLA automation.
   - Implemented: assignee, priority, due date, filters.
   - Missing: SLA breach detection, escalation rules, notifications, saved/shared queues.

4. Export is approved JSON only.
   - Missing: durable export artifact provider, CSV export, webhook, SFTP, object-store export artifact, claims-system delivery.

5. Auth is development-only.
   - Current: local demo login sends `X-Actor` and `X-Role` headers.
   - Missing: real auth, tenant isolation, SSO/token validation, user directory.

6. Search is not implemented.
   - Missing: packet search endpoint, review task search/filter hardening, eventual `SearchProvider`.

7. Provider configuration is read-only.
   - Current: safe status/config metadata.
   - Missing: validated config preview/apply workflow, still without secrets or runtime unsafe mutation.

## Recommended Next Batch 1: Source Document Viewer And OCR Artifacts

Start here if the goal is to make the product feel more real to reviewers.

Agent allocation:

- `neurodocops-api-rbac-engineer`: add parser/OCR artifact model and endpoints.
- `vigolium-ui-ux-designer`: build source document viewer panel in packet workspace.
- `neurodocops-qa-release-engineer`: cover API/UI contracts and no-secret behavior.
- `neurodocops-docs-product-engineer`: update system flow/API/web docs.

Implementation targets:

1. Persist OCR/parser artifacts per document:
   - provider name
   - parser mode
   - page count if available
   - extracted text summary
   - fallback reason if used
   - checksum/source reference metadata without exposing object keys/secrets
2. Add API endpoint to read document parser artifacts.
3. Add packet detail panel that shows:
   - uploaded source file
   - parser mode
   - extracted text
   - field citations/correction notes
4. Keep this honest:
   - no fake bounding boxes
   - no fake scanned OCR
   - no browser-side parser as workflow truth

Acceptance criteria:

- Reviewer can see how each document was parsed.
- PDF embedded-text extraction is distinguishable from fallback text.
- Audit and provider metadata remain secret-safe.
- Backend tests and frontend build pass.

Suggested tests:

```text
tests/test_source_document_upload_api.py
tests/test_provider_registry.py
tests/test_workflow_service.py
tests/test_api.py
```

## Recommended Next Batch 2: Export Delivery Provider

Start here if the goal is backend/product integration depth.

Agent allocation:

- `neurodocops-worker-infra-engineer`: export artifact provider and object-store write.
- `neurodocops-api-rbac-engineer`: export API response and RBAC/audit behavior.
- `neurodocops-qa-release-engineer`: export guardrail and artifact tests.
- `neurodocops-docs-product-engineer`: API/system-flow/export docs.

Implementation targets:

1. Add `ExportProvider` contract.
2. Implement local object-store export artifact provider.
3. On approved export, write JSON artifact to object store.
4. Return export artifact metadata from API.
5. Add artifact download endpoint.
6. Audit export artifact creation.

Acceptance criteria:

- Export creates durable artifact.
- Export artifact can be downloaded by authorized roles.
- Reviewer/auditor still cannot export.
- Export remains blocked unless packet approved and all review tasks resolved.

## Recommended Next Batch 3: SLA And Escalation Rules

Start here if the goal is operations management.

Agent allocation:

- `neurodocops-api-rbac-engineer`: SLA state model and workflow rules.
- `vigolium-ui-ux-designer`: overdue/escalated queue states.
- `neurodocops-qa-release-engineer`: due date and escalation tests.
- `neurodocops-docs-product-engineer`: update review operations docs.

Implementation targets:

1. Add computed SLA status from `due_at`:
   - `on_track`
   - `due_soon`
   - `overdue`
2. Add API queue filter:
   - `overdue=true`
   - `due_soon=true`
3. Add escalation metadata:
   - `escalated_at`
   - `escalated_by`
   - `escalation_reason`
4. Add manager-only escalation action.
5. Add audit event `review_task_escalated`.

Acceptance criteria:

- Due dates become operational, not cosmetic.
- Escalation is manager/admin-controlled.
- Auditor can read escalation history.
- Integration cannot mutate human queue.

## Recommended Next Batch 4: Basic Search Provider Foundation

Start here if the goal is making the system usable with more packets.

Agent allocation:

- `neurodocops-api-rbac-engineer`: search API and repository search.
- `vigolium-ui-ux-designer`: search/filter UI.
- `neurodocops-docs-product-engineer`: document `SearchProvider` roadmap.

Implementation targets:

1. Add packet search endpoint over:
   - claim reference
   - claimant name
   - loss type
   - packet status
2. Add review queue search over:
   - claim reference
   - claimant name
   - task reason
   - assignee
3. Keep implementation repository-backed first.
4. Document future `SearchProvider` for Postgres FTS/OpenSearch/etc.

Acceptance criteria:

- Packet list and review queue become searchable.
- RBAC still controls visibility.
- Tests cover status/search/role behavior.

## Recommended Next Batch 5: Auth/Tenant Foundation Design

Start here only if the goal is preparing a pilot/enterprise path.

Agent allocation:

- `neurodocops-api-rbac-engineer`: tenant and identity boundary design.
- `neurodocops-docs-product-engineer`: production auth/tenant docs.
- `neurodocops-qa-release-engineer`: migration and RBAC regression plan.

Implementation targets:

1. Define tenant model and packet tenant field.
2. Define `IdentityProvider` / `PermissionProvider` boundary.
3. Preserve dev-header mode for local tests.
4. Add tests proving tenant filtering does not leak packets.
5. Do not build fake SSO UI.

Acceptance criteria:

- Clear tenant-aware API direction.
- Dev mode still works.
- No production-auth claims until a real provider is integrated.

## Files To Inspect First In The Next Session

Start with these files before editing:

```text
docs/agent-team-handoff.md
docs/system-flow.md
docs/first-surface-operating-model.md
docs/project-plan.md
services/api/neurodocops_api/main.py
packages/domain/neurodocops_domain/models.py
packages/workflow/neurodocops_workflow/service.py
packages/providers/neurodocops_providers/registry.py
packages/providers/neurodocops_providers/insurance.py
packages/security/neurodocops_security/rbac.py
services/web/src/main.jsx
services/web/src/styles.css
tests/test_api.py
tests/test_workflow_service.py
tests/test_source_document_upload_api.py
```

## Verification Rules For Next Agents

Minimum non-smoke release gate:

```bash
.venv/bin/pytest -q
npm run build        # from services/web
docker compose -f infra/docker-compose.yml config
```

Add targeted tests for the feature first, then full test suite.

Only run stack smoke or `scripts/server_switch.py on` if the user permits smoke testing/restart. If prohibited, do not run them.

## Commit Guidance

Before committing:

1. Run `git status --short`.
2. Review `git diff --stat`.
3. Run `git diff --cached --check` after staging.
4. Scan staged files for real secrets.
5. Local demo passwords in `services/web/src/main.jsx` are expected dev fixtures; real API keys/private keys/tokens are not.
6. Use concise commit messages matching repo style.
7. Never force push.
