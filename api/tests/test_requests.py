import importlib


StudentRequest = importlib.import_module("app.models.student_request").StudentRequest


def _create_request(client, headers, payload):
    return client.post("/api/v1/requests", headers=headers, json=payload)


def test_create_request(client, make_headers, request_payload):
    response = _create_request(client, make_headers(), request_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["request_id"].startswith("REQ-")
    assert data["protocol"].startswith("FIAP-LAB-REQ-")
    assert data["assigned_department"] == "Academic Services"


def test_get_request(client, make_headers, request_payload):
    created = _create_request(client, make_headers(), request_payload).json()

    response = client.get(f"/api/v1/requests/{created['request_id']}", headers=make_headers(request_id="req-get-request"))

    assert response.status_code == 200
    assert response.json()["request_id"] == created["request_id"]


def test_list_requests_and_isolation(client, make_headers, request_payload):
    _create_request(client, make_headers(student_id="grupo-01", request_id="req-list-1"), request_payload)
    _create_request(client, make_headers(student_id="grupo-02", request_id="req-list-2"), {**request_payload, "summary": "Other group request"})

    response = client.get("/api/v1/requests", headers=make_headers(student_id="grupo-01", request_id="req-list-main"))

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["lab_student_id"] == "grupo-01"


def test_update_request(client, db_session, make_headers, request_payload):
    created = _create_request(client, make_headers(), request_payload).json()

    response = client.patch(
        f"/api/v1/requests/{created['request_id']}",
        headers=make_headers(request_id="req-update-request"),
        json={"status": "resolved", "priority": "high", "assigned_department": "technology"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["priority"] == "high"
    assert data["assigned_department"] == "Technology Support"
    request_row = db_session.get(StudentRequest, created["request_id"])
    assert request_row.updated_at is not None


def test_create_request_student_not_found(client, make_headers, request_payload):
    response = _create_request(client, make_headers(), {**request_payload, "student_id": "STU999"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"
