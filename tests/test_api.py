from fastapi.testclient import TestClient

from neurodocops.api import create_app
from neurodocops.service import ClaimPacketWorkflowService
from packages.jobs.neurodocops_jobs import InMemoryJobQueue, JobProcessor, JobStatus, process_next_job
from packages.storage.neurodocops_storage import InMemoryObjectStore, InMemoryPacketRepository


def make_client() -> TestClient:
    service = ClaimPacketWorkflowService(repository=InMemoryPacketRepository())
    return TestClient(create_app(service=service, job_queue=InMemoryJobQueue()))


def test_ready_reports_active_providers() -> None:
    client = make_client()

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["service"] == "api"
    assert "providers" in body
    providers = {provider["kind"]: provider for provider in body["providers"]}
    assert providers["ocr"]["name"] == "mock"
    assert providers["ocr"]["adapter"] == "MockOCRProvider"
    assert providers["extraction"]["name"] == "rule_based_insurance"
    assert providers["extraction"]["adapter"] == "RuleBasedInsuranceExtractionProvider"
    assert "DATABASE_URL" not in response.text
    assert "REDIS_URL" not in response.text
    assert "OBJECT_STORAGE_SECRET_KEY" not in response.text


def test_claim_packet_api_happy_path() -> None:
    client = make_client()

    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-2002",
            "claimant_name": "Jordan Lee",
            "loss_type": "property",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-2002 and policy number P-200."},
                {"filename": "incident.pdf", "text": "Incident report for accident and loss date 2026-05-01."},
                {"filename": "identity.pdf", "text": "National ID identity document for Jordan Lee."},
                {"filename": "invoice.pdf", "text": "Repair invoice amount due 900 USD."},
            ],
        },
    )
    assert create_response.status_code == 201
    packet_id = create_response.json()["id"]

    classify_response = client.post(f"/claim-packets/{packet_id}/classify")
    assert classify_response.status_code == 200
    assert classify_response.json()["documents"][0]["document_type"] == "claim_form"

    extract_response = client.post(f"/claim-packets/{packet_id}/extract")
    assert extract_response.status_code == 200
    assert extract_response.json()["status"] == "extracted"

    checklist_response = client.post(f"/claim-packets/{packet_id}/checklist")
    assert checklist_response.status_code == 200
    assert checklist_response.json()["status"] == "needs_review"
    assert checklist_response.json()["review_tasks"]

    review_response = client.post(
        f"/claim-packets/{packet_id}/review",
        json={"decision": "approve", "reviewer": "claims.ops@example.com"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"

    export_response = client.post(f"/claim-packets/{packet_id}/export")
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "exported"
    assert export_response.json()["open_review_tasks"] == 0
    assert export_response.json()["documents"]

    audit_response = client.get(f"/claim-packets/{packet_id}/audit")
    assert audit_response.status_code == 200
    assert len(audit_response.json()) == 6


def test_api_export_before_approval_returns_conflict() -> None:
    client = make_client()

    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-3003",
            "claimant_name": "Morgan Fox",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-3003 and policy number P-300."}
            ],
        },
    )
    packet_id = create_response.json()["id"]

    export_response = client.post(f"/claim-packets/{packet_id}/export")

    assert export_response.status_code == 409
    assert "approved" in export_response.json()["detail"]


def test_uploaded_source_document_can_be_previewed() -> None:
    repository = InMemoryPacketRepository()
    object_store = InMemoryObjectStore()
    service = ClaimPacketWorkflowService(repository=repository)
    client = TestClient(create_app(service=service, job_queue=InMemoryJobQueue(), object_store=object_store))
    create_response = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-SRC-1", "claimant_name": "Source User", "loss_type": "auto"},
    )
    packet_id = create_response.json()["id"]
    source_bytes = b"synthetic source document bytes"

    upload_response = client.post(
        f"/claim-packets/{packet_id}/documents",
        files={"file": ("source.txt", source_bytes, "text/plain")},
        data={"text": "Claim form with claim number CLM-SRC-1 and policy number POL-SRC."},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["documents"][0]["id"]

    source_response = client.get(f"/claim-packets/{packet_id}/documents/{document_id}/source")

    assert source_response.status_code == 200
    assert source_response.content == source_bytes
    assert source_response.headers["content-type"].startswith("text/plain")


def test_reviewer_can_correct_field_and_export_reflects_audit_proof() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-CORR-1",
            "claimant_name": "Correction User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-CORR-1 and policy number POL-CORR. Loss date 2026-05-03."},
                {"filename": "incident.pdf", "text": "Incident report for accident with incident date 2026-05-03 and loss date 2026-05-03."},
                {"filename": "identity.pdf", "text": "Passport identity document for Correction User."},
                {"filename": "invoice.pdf", "text": "Repair invoice amount due 1200 USD."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    client.post(f"/claim-packets/{packet_id}/classify")
    extract_response = client.post(f"/claim-packets/{packet_id}/extract")
    claim_document = next(document for document in extract_response.json()["documents"] if document["document_type"] == "claim_form")

    correction_response = client.post(
        f"/claim-packets/{packet_id}/documents/{claim_document['id']}/fields/claim_number/correct",
        headers={"X-Role": "reviewer", "X-Actor": "reviewer@example.com"},
        json={"value": "CLM-CORR-1A", "reviewer": "ignored@example.com", "notes": "Corrected from carrier portal."},
    )
    assert correction_response.status_code == 200
    corrected_field = next(
        field
        for document in correction_response.json()["documents"]
        for field in document["extracted_fields"]
        if field["name"] == "claim_number"
    )
    assert corrected_field["value"] == "CLM-CORR-1A"
    assert corrected_field["confidence"] == 1.0

    client.post(f"/claim-packets/{packet_id}/checklist")
    client.post(f"/claim-packets/{packet_id}/review", json={"decision": "approve", "reviewer": "manager@example.com"})
    export_response = client.post(f"/claim-packets/{packet_id}/export")
    assert export_response.status_code == 200
    assert "CLM-CORR-1A" in export_response.json()["fields"].values()

    audit_response = client.get(f"/claim-packets/{packet_id}/audit")
    correction_events = [event for event in audit_response.json() if event["action"] == "field_corrected"]
    assert correction_events
    assert correction_events[0]["actor"] == "reviewer@example.com"
    assert correction_events[0]["detail"]["previous_value"] == "CLM-CORR-1"


def test_auditor_role_can_read_but_cannot_create_or_export() -> None:
    client = make_client()

    list_response = client.get("/claim-packets", headers={"X-Role": "auditor", "X-Actor": "audit@example.com"})
    assert list_response.status_code == 200

    admin_create_response = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-RBAC-1", "claimant_name": "Audit User", "loss_type": "auto"},
    )
    packet_id = admin_create_response.json()["id"]

    create_response = client.post(
        "/claim-packets",
        headers={"X-Role": "auditor", "X-Actor": "audit@example.com"},
        json={"claim_reference": "CLM-RBAC-1B", "claimant_name": "Audit User", "loss_type": "auto"},
    )
    assert create_response.status_code == 403
    assert "packet:create" in create_response.json()["detail"]

    export_response = client.post(
        f"/claim-packets/{packet_id}/export",
        headers={"X-Role": "auditor", "X-Actor": "audit@example.com"},
    )
    assert export_response.status_code == 403
    assert "export:packet" in export_response.json()["detail"]


def test_reviewer_role_cannot_export_packet() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-RBAC-2", "claimant_name": "Reviewer User", "loss_type": "auto"},
    )
    packet_id = create_response.json()["id"]

    export_response = client.post(
        f"/claim-packets/{packet_id}/export",
        headers={"X-Role": "reviewer", "X-Actor": "reviewer@example.com"},
    )
    assert export_response.status_code == 403
    assert "export:packet" in export_response.json()["detail"]


def test_reviewer_role_can_process_and_review_packet() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-RBAC-3",
            "claimant_name": "Reviewer User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-RBAC-3 and policy number P-RBAC."},
                {"filename": "incident.pdf", "text": "Incident report for accident and loss date 2026-05-01."},
                {"filename": "identity.pdf", "text": "National ID identity document for Reviewer User."},
                {"filename": "invoice.pdf", "text": "Repair invoice amount due 900 USD."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    headers = {"X-Role": "reviewer", "X-Actor": "reviewer@example.com"}

    process_response = client.post(f"/claim-packets/{packet_id}/process", headers=headers)
    assert process_response.status_code == 202

    classify_response = client.post(f"/claim-packets/{packet_id}/classify", headers=headers)
    assert classify_response.status_code == 200
    extract_response = client.post(f"/claim-packets/{packet_id}/extract", headers=headers)
    assert extract_response.status_code == 200
    checklist_response = client.post(f"/claim-packets/{packet_id}/checklist", headers=headers)
    assert checklist_response.status_code == 200

    review_response = client.post(
        f"/claim-packets/{packet_id}/review",
        headers=headers,
        json={"decision": "approve", "reviewer": "reviewer@example.com"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"


def test_invalid_role_returns_forbidden() -> None:
    client = make_client()

    response = client.get("/claim-packets", headers={"X-Role": "superuser", "X-Actor": "bad@example.com"})

    assert response.status_code == 403
    assert "Unsupported role" in response.json()["detail"]


def test_api_enqueues_packet_processing_job() -> None:
    repository = InMemoryPacketRepository()
    queue = InMemoryJobQueue()
    service = ClaimPacketWorkflowService(repository=repository)
    client = TestClient(create_app(service=service, job_queue=queue))

    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-JOB-1",
            "claimant_name": "Taylor Job",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-JOB-1 and policy number P-JOB."},
                {"filename": "incident.pdf", "text": "Incident report for accident and loss date 2026-05-01."},
                {"filename": "identity.pdf", "text": "National ID identity document for Taylor Job."},
                {"filename": "invoice.pdf", "text": "Repair invoice amount due 900 USD."},
            ],
        },
    )
    packet_id = create_response.json()["id"]

    enqueue_response = client.post(f"/claim-packets/{packet_id}/process")

    assert enqueue_response.status_code == 202
    job_id = enqueue_response.json()["id"]
    assert enqueue_response.json()["status"] == JobStatus.QUEUED.value

    status_response = client.get(f"/jobs/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["packet_id"] == packet_id

    assert process_next_job(queue, JobProcessor(service), timeout_seconds=0) is True

    completed_status = client.get(f"/jobs/{job_id}").json()
    assert completed_status["status"] == JobStatus.SUCCEEDED.value
    assert client.get(f"/claim-packets/{packet_id}").json()["status"] == "needs_review"
