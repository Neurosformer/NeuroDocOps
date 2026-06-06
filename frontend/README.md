# NeuroDocOps Frontend

Lean React/Vite reviewer console adapted from the `vagescaffolds/NeuroDocopsanything.zip` concept, but wired directly to the FastAPI backend instead of the scaffold's mock API routes.

## Run Locally

Start the backend from the repo root:

```bash
uvicorn neurodocops.api:app --reload
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend uses `http://localhost:8000` by default. Override with:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Current Scope

- Packet dashboard.
- Claim packet intake using text-based document payloads.
- Packet workspace with classify, extract, checklist, review, approve, and export actions.
- Document-level extracted fields with confidence and citations.
- Checklist panel.
- Review tasks panel.
- Audit timeline.
- Export JSON preview.

## Known Gaps

- No real file upload yet; the backend currently accepts document text.
- No field correction endpoint yet.
- No task-level review endpoint yet.
- No auth/tenant frontend yet.
