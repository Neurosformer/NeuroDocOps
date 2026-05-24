# API Guide

Run locally:

```bash
uvicorn neurodocops.api:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Create a document:

```bash
curl -X POST http://localhost:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{"filename":"invoice-1001.pdf","text":"Invoice 1001 for purchase order PO-445. Amount due 1250 USD."}'
```

Classify, extract, and review:

```bash
curl -X POST http://localhost:8000/documents/{document_id}/classify
curl -X POST http://localhost:8000/documents/{document_id}/extract
curl -X POST http://localhost:8000/documents/{document_id}/review \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approve","reviewer":"ops@example.com","notes":"Validated against source document"}'
```

View audit events:

```bash
curl http://localhost:8000/documents/{document_id}/audit
```
