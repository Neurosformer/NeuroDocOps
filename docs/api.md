# API Guide

The MVP API is packet-first and models the first wedge: insurance claims document packets. It is intentionally in-memory so the workflow can be validated before choosing storage, OCR, queue, and model providers.

Run locally:

```bash
uvicorn neurodocops.api:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Create a claim packet:

```bash
curl -X POST http://localhost:8000/claim-packets \
  -H 'Content-Type: application/json' \
  -d '{
    "claim_reference":"CLM-1001",
    "claimant_name":"Amina Rahman",
    "loss_type":"auto",
    "documents":[
      {"filename":"claim-form.pdf","text":"Claim form for claim number CLM-1001 and policy number POL-42."},
      {"filename":"incident-report.pdf","text":"Incident report for accident with loss date 2026-05-01."},
      {"filename":"identity.pdf","text":"Passport identity document for claimant Amina Rahman."},
      {"filename":"repair-invoice.pdf","text":"Repair invoice for vehicle damage. Amount due 1250 USD."}
    ]
  }'
```

Run the workflow:

```bash
curl -X POST http://localhost:8000/claim-packets/{packet_id}/classify
curl -X POST http://localhost:8000/claim-packets/{packet_id}/extract
curl -X POST http://localhost:8000/claim-packets/{packet_id}/checklist
curl -X POST http://localhost:8000/claim-packets/{packet_id}/review \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approve","reviewer":"claims.ops@example.com","notes":"Validated evidence."}'
curl -X POST http://localhost:8000/claim-packets/{packet_id}/export
```

View audit events:

```bash
curl http://localhost:8000/claim-packets/{packet_id}/audit
```
