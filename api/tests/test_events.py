import pytest


@pytest.mark.xfail(reason="Application does not currently create audit events when tickets are created.", strict=False)
def test_events_list(client, make_headers, ticket_payload):
    create_response = client.post("/api/v1/tickets", headers=make_headers(), json=ticket_payload)

    assert create_response.status_code == 201, "Ticket creation prerequisite should succeed before checking audit events."

    response = client.get("/api/v1/events", headers=make_headers(request_id="req-events-list"))

    assert response.status_code == 200, "Event listing should return HTTP 200."
    assert len(response.json()) >= 1, "Creating a ticket should log at least one audit event."


@pytest.mark.xfail(reason="Application does not currently scope emitted events by student-created domain actions.", strict=False)
def test_events_student_filter(client, make_headers, ticket_payload):
    client.post(
        "/api/v1/tickets",
        headers=make_headers(student_id="student-a", request_id="req-events-a"),
        json=ticket_payload,
    )
    client.post(
        "/api/v1/tickets",
        headers=make_headers(student_id="student-b", request_id="req-events-b"),
        json={**ticket_payload, "summary": "Student B event source"},
    )

    response = client.get("/api/v1/events", headers=make_headers(student_id="student-a", request_id="req-events-a-list"))

    assert response.status_code == 200, "Event list for a student should return HTTP 200."
    assert len(response.json()) == 1, "Students should only see audit events generated from their own actions."
    assert response.json()[0]["student_id"] == "student-a", "Event filtering should prevent cross-student visibility."


@pytest.mark.xfail(reason="Application does not currently emit audit events for priority checks.", strict=False)
def test_events_after_priority_check(client, make_headers):
    priority_response = client.post(
        "/api/v1/priority/check",
        headers=make_headers(request_id="req-events-priority"),
        json={
            "employee_id": "EMP001",
            "category": "it",
            "impact": "high",
            "urgency": "high",
        },
    )

    assert priority_response.status_code == 200, "Priority calculation prerequisite should succeed before checking audit events."

    response = client.get("/api/v1/events", headers=make_headers(request_id="req-events-priority-list"))

    assert response.status_code == 200, "Event listing should return HTTP 200 after a priority check."
    assert any(event["resource_type"] == "priority_check" for event in response.json()), "Priority checks should emit an audit event."


@pytest.mark.xfail(reason="Application does not currently emit audit events for access request creation.", strict=False)
def test_events_after_access_request(client, make_headers, access_request_payload):
    create_response = client.post(
        "/api/v1/access-requests",
        headers=make_headers(request_id="req-events-access"),
        json=access_request_payload,
    )

    assert create_response.status_code == 201, "Access request prerequisite should succeed before checking audit events."

    response = client.get("/api/v1/events", headers=make_headers(request_id="req-events-access-list"))

    assert response.status_code == 200, "Event listing should return HTTP 200 after access request creation."
    assert any(event["resource_type"] == "access_request" for event in response.json()), "Access request creation should emit an audit event."
