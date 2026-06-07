---
name: neurodocops-team
description: Use when coordinating NeuroDocOps agent-team work across API/RBAC, worker/infra, web UI, QA/release, and docs/product tasks.
---

# NeuroDocOps Team Workflow

Use this skill when the user asks for a real DevOps/product team, coherent teamwork, or multi-area NeuroDocOps execution.

Team roles:
- `neurodocops-devops-lead`: coordinates architecture, handoffs, priorities, and final integration.
- `neurodocops-api-rbac-engineer`: owns API routes, workflow contracts, provider metadata, RBAC, and backend tests.
- `neurodocops-worker-infra-engineer`: owns worker queue, storage, Docker Compose, MinIO, Redis, Postgres, and one-click stack scripts.
- `vigolium-ui-ux-designer`: owns `services/web` high-trust dark proof/evidence console direction.
- `neurodocops-qa-release-engineer`: owns regression checks, build checks, and validation summaries.
- `neurodocops-docs-product-engineer`: owns README/docs/product language tied to implemented behavior.

Operating model:
1. Inspect current files and git state before editing.
2. Assign independent review or research tasks in parallel where useful.
3. Implement the smallest coherent change in the primary session.
4. Keep API, worker, web, infra, tests, and docs aligned.
5. Verify with backend tests, frontend build, and Compose config when relevant.
6. Report completed work, verification results, and remaining risks.

Project invariants:
- Do not collapse services back into one toy process.
- Do not enable paid/live OCR or model providers by default.
- Do not remove human approval before export.
- Do not make UI claims unsupported by backend behavior.
- Do not copy Vigolium assets, logos, exact text, screenshots, or proprietary layout.
