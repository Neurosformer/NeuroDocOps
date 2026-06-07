---
name: vigolium-ui
description: Use when designing or reviewing NeuroDocOps frontend UI/UX, especially requests mentioning Vigolium, dark console design, evidence workflows, RBAC visibility, review workstations, or services/web.
---

# Vigolium-Inspired NeuroDocOps UI Skill

Use this skill for NeuroDocOps web UI/UX work in `services/web/`.

## Design Language

Use Vigolium as inspiration for:

- dark, serious, security-grade console feel
- proof-first presentation
- high-contrast panels
- concise trust-building copy
- validated result language
- dense operational dashboards
- strong call-to-action hierarchy
- credible enterprise product framing

Do not copy Vigolium assets, logo, exact text, screenshots, or proprietary layout. Translate the trend into NeuroDocOps’ domain: claims packet evidence operations.

## NeuroDocOps Product Translation

Vigolium says “validated proof your team can act on.” NeuroDocOps should say the equivalent for claims packets:

- validated evidence fields
- source citations
- missing evidence checklist
- review-ready packets
- human approval gates
- export proof
- immutable audit trail direction
- RBAC-aware workflow actions

## UI Rules

- Lead with operational status: review risk, evidence completeness, open tasks, export readiness.
- Make approval/export safety obvious.
- Surface role and permission context where relevant.
- Use cards only when they communicate a real workflow state.
- Prefer compact proof panels over decorative dashboards.
- Keep mobile layout usable.
- Do not add UI for backend features that do not exist.

## Useful Screen Patterns

- Dashboard: “Packet Readiness”, “Open Evidence Gaps”, “Awaiting Approval”, “Exported With Audit”.
- Packet Detail: evidence documents left, extracted fields/citations center, checklist/review/audit right.
- Review Actions: classify, extract, checklist, process queued, request changes, approve, export.
- RBAC: show current dev role and disabled states for unauthorized actions once API supports it.
- Audit: chronological proof timeline, actor, action, timestamp, details.

## Implementation Checklist

1. Inspect current React and CSS first.
2. Keep React + Vite.
3. Avoid framework rewrites.
4. Update CSS variables/design tokens before scattering one-off colors.
5. Run `npm run build` after frontend changes.
6. Keep API assumptions aligned with FastAPI routes.
