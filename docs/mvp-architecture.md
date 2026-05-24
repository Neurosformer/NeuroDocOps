# MVP Architecture

NeuroDocOps starts as a document workflow engine, not a generic PDF chat app. The first implementation keeps infrastructure replaceable while proving the core product loop: ingest, classify, extract, review, approve, and audit.

## Current Components

```text
FastAPI API
  -> DocumentWorkflowService
  -> In-memory document store
  -> In-memory audit event stream
  -> Pydantic domain models
```

The in-memory service is intentional for the first milestone. It lets the team validate workflow behavior, API contracts, review states, and audit requirements before committing to database, OCR, queue, storage, and model providers.

## Product Loop

1. Create a document record with OCR text or extracted text.
2. Classify the document into a regulated workflow type.
3. Extract structured fields with confidence scores and citations.
4. Route uncertain fields to human review.
5. Approve reviewed records.
6. Preserve audit events for ingestion, classification, extraction, and review.

## Next Infrastructure Decisions

- Replace in-memory storage with Postgres.
- Add object storage for original documents and page images.
- Add OCR adapters for Azure Document Intelligence, Google Document AI, AWS Textract, or open-source OCR.
- Add async processing for large files and batches.
- Add tenant-aware authentication and role-based access control.
- Add export jobs for CSV, Excel, JSON, webhooks, and API integrations.
