from neurodocops.models import DocumentCreate, DocumentStatus, DocumentType, ReviewDecision, ReviewRequest
from neurodocops.service import DocumentWorkflowService


def test_ingest_classify_extract_and_review_invoice_workflow() -> None:
    service = DocumentWorkflowService()
    document = service.ingest_document(
        DocumentCreate(
            filename="invoice-1001.pdf",
            text="Invoice 1001 for purchase order PO-445. Amount due 1250 USD.",
        )
    )

    assert document.status == DocumentStatus.INGESTED

    classified = service.classify_document(document.id)
    assert classified.document_type == DocumentType.INVOICE
    assert classified.status == DocumentStatus.CLASSIFIED

    extracted = service.extract_fields(document.id)
    assert extracted.status == DocumentStatus.NEEDS_REVIEW
    assert [field.name for field in extracted.extracted_fields] == ["source_filename", "invoice_summary"]
    assert extracted.extracted_fields[1].citation.page == 1

    reviewed = service.complete_review(
        document.id,
        ReviewRequest(decision=ReviewDecision.APPROVE, reviewer="ops@example.com", notes="Validated against source PDF"),
    )
    assert reviewed.status == DocumentStatus.APPROVED

    audit_events = service.list_audit_events(document.id)
    assert [event.action.value for event in audit_events] == [
        "document_ingested",
        "document_classified",
        "fields_extracted",
        "review_completed",
    ]


def test_unknown_document_type_routes_to_review() -> None:
    service = DocumentWorkflowService()
    document = service.ingest_document(DocumentCreate(filename="notes.pdf", text="Miscellaneous uploaded notes."))

    extracted = service.extract_fields(document.id)

    assert extracted.document_type == DocumentType.UNKNOWN
    assert extracted.status == DocumentStatus.NEEDS_REVIEW
    assert extracted.extracted_fields[1].confidence < 0.6
