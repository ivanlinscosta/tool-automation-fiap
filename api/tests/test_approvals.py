def _create_approval(client, headers, payload):
    return client.post("/api/v1/approval-requests", headers=headers, json=payload)


def test_create_approval_request_high_risk(client, make_headers, approval_request_payload):
    response = _create_approval(client, make_headers(), {**approval_request_payload, "risk": "high"})

    assert response.status_code == 201
    data = response.json()
    assert data["approval_id"].startswith("APR-")
    assert data["status"] == "pending_human_approval"
    assert data["requires_human_approval"] is True


def test_create_approval_request_low_risk(client, make_headers, approval_request_payload):
    response = _create_approval(client, make_headers(request_id="req-approval-low"), {**approval_request_payload, "risk": "low"})

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "auto_approved"
    assert data["approved_by"] == "system"


def test_get_approval_request(client, make_headers, approval_request_payload):
    created = _create_approval(client, make_headers(), approval_request_payload).json()

    response = client.get(f"/api/v1/approval-requests/{created['approval_id']}", headers=make_headers(request_id="req-approval-get"))

    assert response.status_code == 200
    assert response.json()["approval_id"] == created["approval_id"]


def test_decide_approval_request(client, make_headers, approval_request_payload):
    created = _create_approval(client, make_headers(), approval_request_payload).json()

    response = client.post(
        f"/api/v1/approval-requests/{created['approval_id']}/decision",
        headers=make_headers(request_id="req-approval-decision"),
        json={"decision": "approve", "approved_by": "analyst@fiap.lab", "comment": "Didactic approval."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["decision"] == "approve"


def test_approval_request_student_not_found(client, make_headers, approval_request_payload):
    response = _create_approval(client, make_headers(), {**approval_request_payload, "student_id": "STU999"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"
