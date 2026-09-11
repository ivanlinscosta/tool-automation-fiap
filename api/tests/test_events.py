def test_events_after_request_creation(client, make_headers, request_payload):
    create_response = client.post("/api/v1/requests", headers=make_headers(), json=request_payload)

    assert create_response.status_code == 201

    response = client.get("/api/v1/events", headers=make_headers(request_id="req-events-list"))

    assert response.status_code == 200
    assert any(event["event_type"] == "request_created" for event in response.json())


def test_events_after_priority_check(client, make_headers):
    priority_response = client.post(
        "/api/v1/priority/check",
        headers=make_headers(request_id="req-events-priority"),
        json={"student_id": "STU001", "category": "technology", "impact": "high", "urgency": "high"},
    )

    assert priority_response.status_code == 200

    response = client.get("/api/v1/events?event_type=priority_checked", headers=make_headers(request_id="req-events-priority-list"))

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["resource_type"] == "priority_check"


def test_events_student_group_filter(client, make_headers, request_payload):
    client.post("/api/v1/requests", headers=make_headers(student_id="grupo-a", request_id="req-a"), json=request_payload)
    client.post("/api/v1/requests", headers=make_headers(student_id="grupo-b", request_id="req-b"), json={**request_payload, "summary": "Outro grupo"})

    response = client.get("/api/v1/events", headers=make_headers(student_id="grupo-a", request_id="req-a-list"))

    assert response.status_code == 200
    assert all(event["student_id"] == "grupo-a" for event in response.json())
