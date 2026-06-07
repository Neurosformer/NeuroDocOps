from fastapi.testclient import TestClient

from neurodocops.api import create_app
from neurodocops.service import ClaimPacketWorkflowService
from packages.jobs.neurodocops_jobs import InMemoryJobQueue, JobProcessor, JobStatus, process_next_job
from packages.storage.neurodocops_storage import InMemoryObjectStore, InMemoryPacketRepository


def make_client() -> TestClient:
    service = ClaimPacketWorkflowService(repository=InMemoryPacketRepository())
    return TestClient(create_app(service=service, job_queue=InMemoryJobQueue()))


def resolve_all_review_tasks(client: TestClient, packet_id: str, headers: dict[str, str] | None = None) -> dict:
    packet = client.get(f"/claim-packets/{packet_id}", headers=headers or {}).json()
    for task in packet["review_tasks"]:
        if task["status"] == "open":
            response = client.post(
                f"/claim-packets/{packet_id}/review-tasks/{task['id']}/resolve",
                headers=headers or {},
                json={"notes": "Resolved during test review."},
            )
            assert response.status_code == 200
            packet = response.json()
    return packet


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


def test_admin_can_read_provider_configuration_without_secrets() -> None:
    client = make_client()

    response = client.get(
        "/system/provider-configuration",
        headers={"X-Actor": "admin@example.com", "X-Role": "admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "read_only_environment_configuration"
    assert body["safety"]["runtime_mutation_supported"] is False
    assert body["safety"]["secrets_exposed"] is False
    slots = {slot["kind"]: slot for slot in body["slots"]}
    assert slots["ocr"]["env_var"] == "NEURODOCOPS_OCR_PROVIDER"
    assert slots["ocr"]["active"]["name"] == "mock"
    assert slots["extraction"]["active"]["name"] == "rule_based_insurance"
    assert "DATABASE_URL" not in response.text
    assert "OBJECT_STORAGE_SECRET_KEY" not in response.text


def test_integration_can_create_packet_and_upload_source_file() -> None:
    repository = InMemoryPacketRepository()
    object_store = InMemoryObjectStore()
    service = ClaimPacketWorkflowService(repository=repository)
    client = TestClient(create_app(service=service, job_queue=InMemoryJobQueue(), object_store=object_store))
    headers = {"X-Actor": "claim-system@example.com", "X-Role": "integration"}

    create_response = client.post(
        "/claim-packets",
        headers=headers,
        json={"claim_reference": "CLM-INT-1", "claimant_name": "Integration User", "loss_type": "auto", "documents": []},
    )
    assert create_response.status_code == 201
    packet_id = create_response.json()["id"]

    source_bytes = b"realistic uploaded source bytes"
    upload_response = client.post(
        f"/claim-packets/{packet_id}/documents",
        headers=headers,
        files={"file": ("claim-source.pdf", source_bytes, "application/pdf")},
        data={"text": "Claim form with claim number CLM-INT-1 and policy number POL-INT."},
    )

    assert upload_response.status_code == 201
    document = upload_response.json()["documents"][0]
    assert document["filename"] == "claim-source.pdf"
    assert document["source_object"]["content_type"] == "application/pdf"

    source_response = client.get(f"/claim-packets/{packet_id}/documents/{document['id']}/source", headers=headers)
    assert source_response.status_code == 200
    assert source_response.content == source_bytes
    assert source_response.headers["content-type"].startswith("application/pdf")


def test_auditor_cannot_create_or_upload_source_file() -> None:
    client = make_client()
    auditor_headers = {"X-Actor": "audit@example.com", "X-Role": "auditor"}

    create_response = client.post(
        "/claim-packets",
        headers=auditor_headers,
        json={"claim_reference": "CLM-AUD-UP", "claimant_name": "Audit User", "loss_type": "auto", "documents": []},
    )
    assert create_response.status_code == 403
    assert "packet:create" in create_response.json()["detail"]

    packet_response = client.post(
        "/claim-packets",
        json={"claim_reference": "CLM-AUD-UP", "claimant_name": "Audit User", "loss_type": "auto", "documents": []},
    )
    packet_id = packet_response.json()["id"]
    upload_response = client.post(
        f"/claim-packets/{packet_id}/documents",
        headers=auditor_headers,
        files={"file": ("audit.pdf", b"bytes", "application/pdf")},
        data={"text": "Claim form with claim number CLM-AUD-UP."},
    )
    assert upload_response.status_code == 403
    assert "document:upload" in upload_response.json()["detail"]


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

    resolve_all_review_tasks(client, packet_id)

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
    assert any(event["action"] == "review_task_resolved" for event in audit_response.json())


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
    resolve_all_review_tasks(client, packet_id)
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

    resolve_all_review_tasks(client, packet_id, headers=headers)

    review_response = client.post(
        f"/claim-packets/{packet_id}/review",
        headers=headers,
        json={"decision": "approve", "reviewer": "reviewer@example.com"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"


def test_reviewer_can_resolve_and_reopen_specific_review_task() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-TASK-1",
            "claimant_name": "Task User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-TASK-1 and policy number P-TASK."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    checklist_response = client.post(f"/claim-packets/{packet_id}/checklist")
    task_id = checklist_response.json()["review_tasks"][0]["id"]
    headers = {"X-Role": "reviewer", "X-Actor": "reviewer@example.com"}

    resolve_response = client.post(
        f"/claim-packets/{packet_id}/review-tasks/{task_id}/resolve",
        headers=headers,
        json={"notes": "Validated missing evidence exception."},
    )
    assert resolve_response.status_code == 200
    resolved_task = next(task for task in resolve_response.json()["review_tasks"] if task["id"] == task_id)
    assert resolved_task["status"] == "resolved"
    assert resolved_task["reviewer"] == "reviewer@example.com"
    assert resolved_task["notes"] == "Validated missing evidence exception."
    assert resolved_task["resolved_at"] is not None

    reopen_response = client.post(
        f"/claim-packets/{packet_id}/review-tasks/{task_id}/reopen",
        headers=headers,
        json={"notes": "Reopened for manager review."},
    )
    assert reopen_response.status_code == 200
    reopened_task = next(task for task in reopen_response.json()["review_tasks"] if task["id"] == task_id)
    assert reopened_task["status"] == "open"
    assert reopened_task["reviewer"] == "reviewer@example.com"
    assert reopened_task["notes"] == "Reopened for manager review."
    assert reopened_task["resolved_at"] is None

    audit_response = client.get(f"/claim-packets/{packet_id}/audit")
    audit_actions = [event["action"] for event in audit_response.json()]
    assert "review_task_resolved" in audit_actions
    assert "review_task_reopened" in audit_actions


def test_reviewer_can_list_and_update_review_task_queue_metadata() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-QUEUE-1",
            "claimant_name": "Queue User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-QUEUE-1 and policy number P-QUEUE."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    checklist_response = client.post(f"/claim-packets/{packet_id}/checklist")
    task_id = checklist_response.json()["review_tasks"][0]["id"]
    headers = {"X-Role": "reviewer", "X-Actor": "reviewer@example.com"}

    update_response = client.patch(
        f"/claim-packets/{packet_id}/review-tasks/{task_id}",
        headers=headers,
        json={"assignee": "reviewer@example.com", "priority": "high", "due_at": "2026-06-10T17:00:00Z", "notes": "Claimed from queue."},
    )

    assert update_response.status_code == 200
    updated_task = next(task for task in update_response.json()["review_tasks"] if task["id"] == task_id)
    assert updated_task["assignee"] == "reviewer@example.com"
    assert updated_task["priority"] == "high"
    assert updated_task["due_at"] == "2026-06-10T17:00:00Z"
    assert updated_task["notes"] == "Claimed from queue."

    queue_response = client.get("/review-tasks", headers=headers, params={"assignee": "reviewer@example.com", "priority": "high"})
    assert queue_response.status_code == 200
    assert [item["task"]["id"] for item in queue_response.json()] == [task_id]


def test_auditor_can_read_review_queue_but_cannot_update_task_assignment() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-QUEUE-RBAC-1",
            "claimant_name": "Queue RBAC User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-QUEUE-RBAC-1 and policy number P-QUEUE."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    task_id = client.post(f"/claim-packets/{packet_id}/checklist").json()["review_tasks"][0]["id"]
    auditor_headers = {"X-Role": "auditor", "X-Actor": "audit@example.com"}

    queue_response = client.get("/review-tasks", headers=auditor_headers)
    assert queue_response.status_code == 200
    assert any(item["task"]["id"] == task_id for item in queue_response.json())

    update_response = client.patch(
        f"/claim-packets/{packet_id}/review-tasks/{task_id}",
        headers=auditor_headers,
        json={"assignee": "audit@example.com"},
    )
    assert update_response.status_code == 403
    assert "review_task:update" in update_response.json()["detail"]


def test_integration_cannot_read_or_update_review_queue() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-QUEUE-RBAC-2",
            "claimant_name": "Integration Queue User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-QUEUE-RBAC-2 and policy number P-QUEUE."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    task_id = client.post(f"/claim-packets/{packet_id}/checklist").json()["review_tasks"][0]["id"]
    headers = {"X-Role": "integration", "X-Actor": "integration@example.com"}

    queue_response = client.get("/review-tasks", headers=headers)
    assert queue_response.status_code == 403
    assert "review_task:read" in queue_response.json()["detail"]

    update_response = client.patch(f"/claim-packets/{packet_id}/review-tasks/{task_id}", headers=headers, json={"assignee": "integration@example.com"})
    assert update_response.status_code == 403
    assert "review_task:update" in update_response.json()["detail"]


def test_review_task_assignment_update_is_audited_with_header_actor() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-QUEUE-AUDIT",
            "claimant_name": "Queue Audit User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-QUEUE-AUDIT and policy number P-QUEUE."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    task_id = client.post(f"/claim-packets/{packet_id}/checklist").json()["review_tasks"][0]["id"]

    response = client.patch(
        f"/claim-packets/{packet_id}/review-tasks/{task_id}",
        headers={"X-Role": "manager", "X-Actor": "manager@example.com"},
        json={"assignee": "reviewer@example.com", "priority": "urgent"},
    )
    assert response.status_code == 200

    audit_response = client.get(f"/claim-packets/{packet_id}/audit", headers={"X-Role": "auditor", "X-Actor": "audit@example.com"})
    events = audit_response.json()
    assignment_events = [event for event in events if event["action"] == "review_task_assigned"]
    update_events = [event for event in events if event["action"] == "review_task_updated"]
    assert assignment_events
    assert update_events
    assert assignment_events[0]["actor"] == "manager@example.com"
    assert assignment_events[0]["detail"]["task_id"] == task_id
    assert assignment_events[0]["detail"]["assignee"] == "reviewer@example.com"


def test_auditor_cannot_resolve_review_task_and_unknown_task_returns_not_found() -> None:
    from uuid import uuid4

    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-TASK-2",
            "claimant_name": "Audit Task User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-TASK-2 and policy number P-TASK."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    checklist_response = client.post(f"/claim-packets/{packet_id}/checklist")
    task_id = checklist_response.json()["review_tasks"][0]["id"]

    denied_response = client.post(
        f"/claim-packets/{packet_id}/review-tasks/{task_id}/resolve",
        headers={"X-Role": "auditor", "X-Actor": "audit@example.com"},
        json={"notes": "Auditor should not mutate."},
    )
    assert denied_response.status_code == 403
    assert "review:complete" in denied_response.json()["detail"]

    missing_response = client.post(
        f"/claim-packets/{packet_id}/review-tasks/{uuid4()}/resolve",
        headers={"X-Role": "reviewer", "X-Actor": "reviewer@example.com"},
        json={"notes": "Missing task."},
    )
    assert missing_response.status_code == 404
    assert "Review task not found" in missing_response.json()["detail"]


def test_packet_approval_requires_all_review_tasks_resolved() -> None:
    client = make_client()
    create_response = client.post(
        "/claim-packets",
        json={
            "claim_reference": "CLM-TASK-3",
            "claimant_name": "Approval Task User",
            "loss_type": "auto",
            "documents": [
                {"filename": "claim-form.pdf", "text": "Claim form with claim number CLM-TASK-3 and policy number P-TASK."},
            ],
        },
    )
    packet_id = create_response.json()["id"]
    client.post(f"/claim-packets/{packet_id}/checklist")

    blocked_review = client.post(
        f"/claim-packets/{packet_id}/review",
        headers={"X-Role": "manager", "X-Actor": "manager@example.com"},
        json={"decision": "approve", "reviewer": "ignored@example.com"},
    )
    assert blocked_review.status_code == 409
    assert "Open review tasks" in blocked_review.json()["detail"]

    resolve_all_review_tasks(client, packet_id, headers={"X-Role": "reviewer", "X-Actor": "reviewer@example.com"})
    approved_review = client.post(
        f"/claim-packets/{packet_id}/review",
        headers={"X-Role": "manager", "X-Actor": "manager@example.com"},
        json={"decision": "approve", "reviewer": "ignored@example.com"},
    )
    assert approved_review.status_code == 200
    assert approved_review.json()["status"] == "approved"


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
