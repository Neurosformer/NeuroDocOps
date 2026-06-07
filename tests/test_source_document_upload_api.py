from fastapi.testclient import TestClient

from neurodocops.api import create_app
from neurodocops.service import ClaimPacketWorkflowService
from packages.jobs.neurodocops_jobs import InMemoryJobQueue, JobProcessor, JobStatus, process_next_job
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
