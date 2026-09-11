def _create_access_request(client, headers, payload):
    return client.post("/api/v1/access-requests", headers=headers, json=payload)


def test_create_access_request_high_risk(client, make_headers, access_request_payload):
    response = _create_access_request(
        client,
        make_headers(),
        {**access_request_payload, "risk": "high"},
    )

    assert response.status_code == 201, "High-risk access requests should be created successfully."
    data = response.json()
    assert data["status"] == "pending_approval", "High-risk requests should wait for human approval."
    assert data["requires_human_approval"] is True, "High-risk requests should require human approval."


def test_create_access_request_low_risk(client, make_headers, access_request_payload):
    response = _create_access_request(
        client,
        make_headers(request_id="req-access-low"),
        {**access_request_payload, "risk": "low"},
    )

    assert response.status_code == 201, "Low-risk access requests should be created successfully."
    data = response.json()
    assert data["status"] == "auto_approved", "Low-risk requests should be auto-approved by the didactic policy."
    assert data["decision"] == "auto_approved", "Low-risk requests should record the auto-approved decision."
    assert data["approved_by"] == "system", "Low-risk requests should record system as the approver."


def test_create_access_request_medium_risk(client, make_headers, access_request_payload):
    response = _create_access_request(
        client,
        make_headers(request_id="req-access-medium"),
        access_request_payload,
    )

    assert response.status_code == 201, "Medium-risk access requests should be created successfully."
    data = response.json()
    assert data["status"] == "pending_approval", "Medium-risk requests should wait for human approval."
    assert data["requires_human_approval"] is True, "Medium-risk requests should require human approval."


def test_get_access_request_success(client, make_headers, access_request_payload):
    create_response = _create_access_request(client, make_headers(), access_request_payload)
    request_id = create_response.json()["request_id"]

    response = client.get(f"/api/v1/access-requests/{request_id}", headers=make_headers(request_id="req-access-get"))

    assert response.status_code == 200, "Fetching a freshly created access request should return HTTP 200."
    assert response.json()["request_id"] == request_id, "Access request lookup should return the same request ID that was created."


def test_get_access_request_not_found(client, make_headers):
    response = client.get("/api/v1/access-requests/AR-9999", headers=make_headers(request_id="req-access-missing"))

    assert response.status_code == 404, "Unknown access requests should return HTTP 404."
    assert response.json()["detail"] == "Access request not found", "Unknown access request responses should include the expected error detail."


def test_approve_access_request(client, make_headers, access_request_payload):
    create_response = _create_access_request(client, make_headers(), access_request_payload)
    request_id = create_response.json()["request_id"]

    response = client.post(
        f"/api/v1/access-requests/{request_id}/approve",
        headers=make_headers(request_id="req-access-approve"),
        json={
            "approved_by": "manager@flowdesk.lab",
            "decision": "approved",
            "decision_comment": "Approved for production support coverage.",
        },
    )

    assert response.status_code == 200, "Approving a pending access request should return HTTP 200."
    assert response.json()["status"] == "approved", "Approved requests should transition to status='approved'."


def test_reject_access_request(client, make_headers, access_request_payload):
    create_response = _create_access_request(
        client,
        make_headers(request_id="req-access-create-reject"),
        access_request_payload,
    )
    request_id = create_response.json()["request_id"]

    response = client.post(
        f"/api/v1/access-requests/{request_id}/approve",
        headers=make_headers(request_id="req-access-reject"),
        json={
            "approved_by": "manager@flowdesk.lab",
            "decision": "rejected",
            "decision_comment": "Rejected pending further justification.",
        },
    )

    assert response.status_code == 200, "Rejecting a pending access request should return HTTP 200."
    assert response.json()["status"] == "rejected", "Rejected requests should transition to status='rejected'."


def test_approve_fields(client, make_headers, access_request_payload):
    create_response = _create_access_request(
        client,
        make_headers(request_id="req-access-create-fields"),
        access_request_payload,
    )
    request_id = create_response.json()["request_id"]

    response = client.post(
        f"/api/v1/access-requests/{request_id}/approve",
        headers=make_headers(request_id="req-access-fields"),
        json={
            "approved_by": "lead@flowdesk.lab",
            "decision": "approved",
            "decision_comment": "Temporary access approved for incident response.",
        },
    )

    assert response.status_code == 200, "Approved access request field validation should return HTTP 200."
    data = response.json()
    assert data["decision"] == "approved", "Approved request should record the decision value."
    assert data["approved_by"] == "lead@flowdesk.lab", "Approved request should record the approver identity."
    assert data["decision_at"] is not None, "Approved request should record a decision timestamp."


def test_access_request_student_id(client, make_headers, access_request_payload):
    response = _create_access_request(
        client,
        make_headers(student_id="student-777", request_id="req-access-student"),
        access_request_payload,
    )

    assert response.status_code == 201, "Access request creation with a student header should succeed."
    assert response.json()["student_id"] == "student-777", "Access request should persist the X-Student-ID header value."
