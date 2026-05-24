# MVP Architecture

NeuroDocOps starts as an insurance claims packet workflow engine, not a generic PDF chat app or raw OCR API. The first implementation proves the core product loop: packet intake, document classification, field extraction, checklist evaluation, human review, approval, export, and audit.

## Current Components

```text
FastAPI API
  -> ClaimPacketWorkflowService
  -> In-memory packet store
  -> In-memory audit event stream
  -> Pydantic domain models
```

The in-memory service is intentional for the first milestone. It lets the team validate workflow behavior, API contracts, review states, checklist logic, and audit requirements before committing to database, OCR, queue, storage, and model providers.

## Product Loop

1. Create a claim packet with claim metadata and OCR text for each source document.
2. Classify included documents such as claim forms, incident reports, identity evidence, medical bills, repair invoices, and policy documents.
3. Extract structured fields with confidence scores and document-level citations.
4. Evaluate the packet completeness checklist.
5. Create review tasks for missing evidence and low-confidence fields.
6. Resolve review tasks and approve the packet.
7. Export approved structured data.
8. Preserve audit events for intake, classification, extraction, checklist evaluation, review, and export.

## Current Workflow API

```text
POST /claim-packets
POST /claim-packets/{packet_id}/classify
POST /claim-packets/{packet_id}/extract
POST /claim-packets/{packet_id}/checklist
POST /claim-packets/{packet_id}/review
POST /claim-packets/{packet_id}/export
GET  /claim-packets/{packet_id}/audit
```

## Next Infrastructure Decisions

- Replace in-memory storage with Postgres.
- Add object storage for original documents and page images.
- Add OCR adapters for Azure Document Intelligence, Google Document AI, AWS Textract, or open-source OCR.
- Add async processing for large files and batches.
- Add tenant-aware authentication and role-based access control.
- Add export jobs for CSV, Excel, JSON, webhooks, and claims-system API integrations.
