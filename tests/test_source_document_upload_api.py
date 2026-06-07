from fastapi.testclient import TestClient

from neurodocops.api import create_app
from neurodocops.service import ClaimPacketWorkflowService
from packages.jobs.neurodocops_jobs import InMemoryJobQueue, JobProcessor, JobStatus, process_next_job
from packages.providers.neurodocops_providers import ProviderRegistry, ProviderSettings
from packages.storage.neurodocops_storage import InMemoryObjectStore, InMemoryPacketRepository


def test_api_uploads_source_document_to_packet_object_store() -> None:
    repository = InMemoryPacketRepository()
    object_store = InMemoryObjectStore(bucket="test-documents")
    service = ClaimPacketWorkflowService(repository=repository)
    client = TestClient(create_app(service=service, job_queue=InMemoryJobQueue(), object_store=object_store))
    create_response = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-UPLOAD-1", "claimant_name": "Upload Claimant", "loss_type": "auto"},
    )
    packet_id = create_response.json()["id"]

    upload_response = client.post(
        f"/claim-packets/{packet_id}/documents",
        files={"file": ("claim form.pdf", b"raw pdf bytes", "application/pdf")},
        data={"text": "Claim form with claim number CLM-UPLOAD-1 and policy number P-UP.", "metadata": '{"source":"test"}'},
    )

    assert upload_response.status_code == 201
    document = upload_response.json()["documents"][0]
    assert document["filename"] == "claim form.pdf"
    assert document["source_object"]["bucket"] == "test-documents"
    assert document["source_object"]["size_bytes"] == len(b"raw pdf bytes")
    assert object_store.get_bytes(document["source_object"]["key"]) == b"raw pdf bytes"

    audit_actions = [event["action"] for event in client.get(f"/claim-packets/{packet_id}/audit").json()]
    assert audit_actions == ["packet_intaked", "document_uploaded"]


def test_api_upload_document_to_missing_packet_returns_404() -> None:
    client = TestClient(create_app(service=ClaimPacketWorkflowService(), job_queue=InMemoryJobQueue(), object_store=InMemoryObjectStore()))

    response = client.post(
        "/claim-packets/00000000-0000-0000-0000-000000000000/documents",
        files={"file": ("claim.pdf", b"raw", "application/pdf")},
        data={"text": "Claim form text."},
    )

    assert response.status_code == 404


def test_api_rejects_empty_source_document_upload() -> None:
    service = ClaimPacketWorkflowService()
    client = TestClient(create_app(service=service, job_queue=InMemoryJobQueue(), object_store=InMemoryObjectStore()))
    packet_id = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-UPLOAD-2", "claimant_name": "Upload Claimant", "loss_type": "auto"},
    ).json()["id"]

    response = client.post(
        f"/claim-packets/{packet_id}/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"text": "Claim form text."},
    )

    assert response.status_code == 400


def test_uploaded_documents_can_be_processed_by_existing_worker_job() -> None:
    repository = InMemoryPacketRepository()
    queue = InMemoryJobQueue()
    service = ClaimPacketWorkflowService(repository=repository)
    client = TestClient(create_app(service=service, job_queue=queue, object_store=InMemoryObjectStore()))
    packet_id = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-UPLOAD-3", "claimant_name": "Upload Claimant", "loss_type": "auto"},
    ).json()["id"]
    uploads = [
        ("claim-form.pdf", "Claim form with claim number CLM-UPLOAD-3 and policy number P-UP."),
        ("incident.pdf", "Incident report for accident and loss date 2026-05-01."),
        ("identity.pdf", "National ID identity document for Upload Claimant."),
        ("invoice.pdf", "Repair invoice amount due 900 USD."),
    ]
    for filename, text in uploads:
        response = client.post(
            f"/claim-packets/{packet_id}/documents",
            files={"file": (filename, f"raw bytes for {filename}".encode(), "application/pdf")},
            data={"text": text},
        )
        assert response.status_code == 201

    enqueue_response = client.post(f"/claim-packets/{packet_id}/process")
    job_id = enqueue_response.json()["id"]
    assert process_next_job(queue, JobProcessor(service), timeout_seconds=0) is True

    assert client.get(f"/jobs/{job_id}").json()["status"] == JobStatus.SUCCEEDED.value
    packet = client.get(f"/claim-packets/{packet_id}").json()
    assert packet["status"] == "needs_review"
    assert all(document["source_object"] for document in packet["documents"])


def test_api_direct_extract_uses_uploaded_pdf_source_bytes() -> None:
    object_store = InMemoryObjectStore(bucket="test-documents")
    client = TestClient(
        create_app(
            job_queue=InMemoryJobQueue(),
            object_store=object_store,
            provider_registry=ProviderRegistry(ProviderSettings(ocr_provider="local_pdf_text")),
        )
    )
    packet_id = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-PDF-API", "claimant_name": "PDF Claimant", "loss_type": "auto"},
    ).json()["id"]

    upload_response = client.post(
        f"/claim-packets/{packet_id}/documents",
        files={"file": ("claim.pdf", embedded_text_pdf("Claim form with claim number CLM-PDF-API and policy number POL-PDF-API."), "application/pdf")},
        data={"text": "fallback claim number WRONG-FORM-TEXT"},
    )
    assert upload_response.status_code == 201

    extract_response = client.post(f"/claim-packets/{packet_id}/extract")

    assert extract_response.status_code == 200
    document = extract_response.json()["documents"][0]
    assert document["document_type"] == "claim_form"
    assert document["ocr_provider"] == "local-pdf-text"
    assert "CLM-PDF-API" in document["ocr_text"]
    assert "WRONG-FORM-TEXT" not in document["ocr_text"]
    fields = {field["name"]: field["value"] for field in document["extracted_fields"]}
    assert fields["claim_number"] == "CLM-PDF-API"
    assert fields["policy_number"] == "POL-PDF-API"


def test_worker_processes_uploaded_pdf_using_source_bytes_not_form_text() -> None:
    object_store = InMemoryObjectStore(bucket="test-documents")
    repository = InMemoryPacketRepository()
    queue = InMemoryJobQueue()

    def load_source_bytes(document):
        return object_store.get_bytes(document.source_object.key) if document.source_object else None

    registry = ProviderRegistry(ProviderSettings(ocr_provider="local_pdf_text"), source_bytes_loader=load_source_bytes)
    service = ClaimPacketWorkflowService(repository=repository, provider_registry=registry, source_bytes_loader=load_source_bytes)
    client = TestClient(create_app(service=service, job_queue=queue, object_store=object_store))
    packet_id = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-PDF-WORKER", "claimant_name": "PDF Claimant", "loss_type": "auto"},
    ).json()["id"]
    client.post(
        f"/claim-packets/{packet_id}/documents",
        files={"file": ("claim.pdf", embedded_text_pdf("Claim form with claim number CLM-PDF-WORKER and policy number POL-PDF-WORKER."), "application/pdf")},
        data={"text": "fallback claim number WRONG-FORM-TEXT"},
    )

    enqueue_response = client.post(f"/claim-packets/{packet_id}/process")
    job_id = enqueue_response.json()["id"]
    assert process_next_job(queue, JobProcessor(service), timeout_seconds=0) is True

    assert client.get(f"/jobs/{job_id}").json()["status"] == JobStatus.SUCCEEDED.value
    packet = client.get(f"/claim-packets/{packet_id}").json()
    document = packet["documents"][0]
    assert packet["status"] == "needs_review"
    assert document["ocr_provider"] == "local-pdf-text"
    assert "CLM-PDF-WORKER" in document["ocr_text"]
    assert "WRONG-FORM-TEXT" not in document["ocr_text"]


def embedded_text_pdf(text: str) -> bytes:
    return f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 64 >>
stream
BT /F1 12 Tf 72 720 Td ({text}) Tj ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
trailer << /Root 1 0 R >>
%%EOF
""".encode("latin-1")
