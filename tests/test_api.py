from fastapi.testclient import TestClient

from neurodocops.api import app


def test_document_api_happy_path() -> None:
    client = TestClient(app)

    create_response = client.post(
        "/documents",
        json={"filename": "claim.pdf", "text": "Claim form for policy P-100 after an incident."},
    )
    assert create_response.status_code == 201
    document_id = create_response.json()["id"]

    classify_response = client.post(f"/documents/{document_id}/classify")
    assert classify_response.status_code == 200
    assert classify_response.json()["document_type"] == "claim_form"

    extract_response = client.post(f"/documents/{document_id}/extract")
    assert extract_response.status_code == 200
    assert extract_response.json()["status"] == "needs_review"

    review_response = client.post(
        f"/documents/{document_id}/review",
        json={"decision": "approve", "reviewer": "reviewer@example.com"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"

    audit_response = client.get(f"/documents/{document_id}/audit")
    assert audit_response.status_code == 200
    assert len(audit_response.json()) == 4
