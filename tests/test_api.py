from fastapi.testclient import TestClient

from neurodocops.api import app


def test_claim_packet_api_happy_path() -> None:
    client = TestClient(app)

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

    audit_response = client.get(f"/claim-packets/{packet_id}/audit")
    assert audit_response.status_code == 200
    assert len(audit_response.json()) == 6
