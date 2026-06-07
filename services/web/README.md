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
- Claim packet intake using text-based document payloads.
- Packet workspace with classify, extract, checklist, review, approve, and export actions.
- Document-level extracted fields with confidence, citations, reviewer correction controls, and audit-backed correction notes.
- Checklist panel.
- Review tasks panel.
- Audit timeline.
- Export JSON preview.
- Dev RBAC context controls that send `X-Actor` and `X-Role` headers to the API.

## Design Direction

The console uses a dark, high-trust evidence operations style inspired by serious security-audit products. The UI should emphasize proof, citations, review exceptions, audit timeline, approval status, and export safety. Vigolium is only inspiration for tone and seriousness; do not copy its assets, logo, exact text, screenshots, or proprietary layout.

## Known Gaps

- No source-file upload UI yet; the backend has a multipart upload endpoint but the current web intake submits text payloads.
- No task-level review resolution endpoint yet; packet approval currently resolves open review tasks together.
- No full auth/tenant frontend yet; current controls are development RBAC headers only.
