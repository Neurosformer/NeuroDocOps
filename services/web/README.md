# NeuroDocOps Web Service

Lean React/Vite reviewer console adapted from the `vagescaffolds/NeuroDocopsanything.zip` concept, but wired directly to the FastAPI backend instead of the scaffold's mock API routes.

## Run Locally

Start the API service from the repo root:

```bash
uvicorn services.api.neurodocops_api.main:app --reload
```

Start the web service:

```bash
cd services/web
npm install
npm run dev
```

The frontend uses `http://localhost:8000` by default. Override with:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Or run the full local stack from the repository root:

```bash
python scripts/server_switch.py on
python scripts/server_switch.py off
```

## Current Scope

- Packet dashboard.
- Claim packet intake using text-based evidence payloads.
- Source-backed packet intake with real file upload to the API/object store.
- Packet workspace with classify, extract, checklist, review, approve, and export actions.
- Document-level extracted fields with confidence, citations, reviewer correction controls, and audit-backed correction notes.
- Source document open/preview/download action when source bytes exist.
- Checklist panel.
- Review tasks panel with task-level resolve/reopen actions, notes, RBAC gating, and audit refresh.
- Reviewer work queue page backed by API task filters, assignee, priority, due date, and queue notes.
- Audit timeline.
- Export JSON preview.
- Dev RBAC context controls that send `X-Actor` and `X-Role` headers to the API.

## Design Direction

The console uses a dark, high-trust evidence operations style inspired by serious security-audit products. The UI should emphasize proof, citations, review exceptions, audit timeline, approval status, and export safety. Vigolium is only inspiration for tone and seriousness; do not copy its assets, logo, exact text, screenshots, or proprietary layout.

The UI should reflect the backend-supported flow in `../../docs/system-flow.md` and should not imply providers or export channels that are not implemented.

## Provider Visibility

The web console should not directly integrate OCR, model, storage, auth, search, telemetry, intake, or export providers. It should call NeuroDocOps API endpoints and display backend-supported provider status, review evidence, citations, audit events, RBAC context, approval state, and export safety.

Local digital-PDF text extraction is a backend provider/parser path. The UI may explain whether a document was parsed locally, supplied with fallback text, or not parsed, but it must not call PDF/OCR libraries in the browser as workflow truth.

Provider configuration is a backend/API-worker concern. A future provider status/configuration view should be read-only first and should never expose credentials, database URLs, Redis URLs, object keys, or storage secrets.

## Known Gaps

- Local PDF text extraction handles embedded text only; scanned/image-only documents still need pasted fallback text or future OCR.
- No page-level PDF viewer, OCR artifact viewer, table viewer, or region-level citation UI yet.
- Review task assignment metadata, priority, due dates, and filterable queue ownership are implemented where backed by the API/UI.
- SLA/escalation automation, notifications, and saved/shared review queue views are still roadmap.
- No full auth/tenant frontend yet; current controls are development RBAC headers only.
- No CSV/webhook/SFTP/export-delivery UI yet; approved JSON export is implemented.
