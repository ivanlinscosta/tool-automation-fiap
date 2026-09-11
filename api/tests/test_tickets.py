from app.models.ticket import Ticket


EXPECTED_TICKET_FIELDS = {
    "ticket_id",
    "status",
    "employee_id",
    "category",
    "priority",
    "assigned_team",
    "queue",
    "summary",
    "description",
    "source",
    "student_id",
    "created_at",
    "updated_at",
}


def _create_ticket(client, headers, payload):
    return client.post("/api/v1/tickets", headers=headers, json=payload)


def test_create_ticket(client, make_headers, ticket_payload):
    response = _create_ticket(client, make_headers(), ticket_payload)

    assert response.status_code == 201, "Ticket creation should return HTTP 201."
    assert response.json()["ticket_id"].startswith("TK-"), "Created tickets should use the TK- prefix."


def test_create_ticket_fields(client, make_headers, ticket_payload):
    response = _create_ticket(client, make_headers(request_id="req-ticket-fields"), ticket_payload)

    assert response.status_code == 201, "Ticket field validation test should receive HTTP 201."
    assert EXPECTED_TICKET_FIELDS.issubset(response.json().keys()), "Created ticket response should contain every expected field."


def test_create_ticket_auto_team(client, make_headers, ticket_payload):
    response = _create_ticket(client, make_headers(request_id="req-ticket-team"), ticket_payload)

    assert response.status_code == 201, "Ticket creation should succeed for IT tickets."
    data = response.json()
    assert data["category"] == "it", "IT tickets should keep the normalized IT category."
    assert data["assigned_team"] == "IT Support", "IT tickets should be assigned to the IT Support team."
    assert data["queue"] == "technical-support", "IT tickets should be routed to the technical-support queue."


def test_get_ticket_success(client, make_headers, ticket_payload):
    create_response = _create_ticket(client, make_headers(), ticket_payload)
    ticket_id = create_response.json()["ticket_id"]

    response = client.get(f"/api/v1/tickets/{ticket_id}", headers=make_headers(request_id="req-ticket-get"))

    assert response.status_code == 200, "Fetching a freshly created ticket should return HTTP 200."
    assert response.json()["ticket_id"] == ticket_id, "Ticket lookup should return the same ticket ID that was created."


def test_get_ticket_not_found(client, make_headers):
    response = client.get("/api/v1/tickets/TK-9999", headers=make_headers(request_id="req-ticket-missing"))

    assert response.status_code == 404, "Unknown tickets should return HTTP 404."
    assert response.json()["detail"] == "Ticket not found", "Unknown ticket responses should include the expected error detail."


def test_list_tickets(client, make_headers, ticket_payload):
    payload_two = {**ticket_payload, "employee_id": "EMP002", "summary": "VPN issue"}
    payload_three = {**ticket_payload, "employee_id": "EMP003", "summary": "Laptop issue", "category": "hr", "urgency": "low"}

    _create_ticket(client, make_headers(request_id="req-ticket-list-1"), ticket_payload)
    _create_ticket(client, make_headers(request_id="req-ticket-list-2"), payload_two)
    _create_ticket(client, make_headers(request_id="req-ticket-list-3"), payload_three)

    response = client.get("/api/v1/tickets", headers=make_headers(request_id="req-ticket-list"))

    assert response.status_code == 200, "Ticket listing should return HTTP 200."
    assert len(response.json()) == 3, "Listing tickets should return every ticket created for the test case."


def test_list_tickets_filter_employee(client, make_headers, ticket_payload):
    _create_ticket(client, make_headers(request_id="req-ticket-employee-1"), ticket_payload)
    _create_ticket(
        client,
        make_headers(request_id="req-ticket-employee-2"),
        {**ticket_payload, "employee_id": "EMP002", "summary": "Need monitor replacement"},
    )

    response = client.get("/api/v1/tickets?employee_id=EMP002", headers=make_headers(request_id="req-ticket-filter-employee"))

    assert response.status_code == 200, "Ticket list filtered by employee should return HTTP 200."
    data = response.json()
    assert len(data) == 1, "Employee filter should return only the matching ticket."
    assert data[0]["employee_id"] == "EMP002", "Employee filter should return the requested employee's ticket."


def test_list_tickets_filter_category(client, make_headers, ticket_payload):
    _create_ticket(client, make_headers(request_id="req-ticket-category-1"), ticket_payload)
    _create_ticket(
        client,
        make_headers(request_id="req-ticket-category-2"),
        {**ticket_payload, "category": "hr", "summary": "Benefits portal question"},
    )

    response = client.get("/api/v1/tickets?category=hr", headers=make_headers(request_id="req-ticket-filter-category"))

    assert response.status_code == 200, "Ticket list filtered by category should return HTTP 200."
    data = response.json()
    assert len(data) == 1, "Category filter should return only the matching ticket."
    assert data[0]["category"] == "hr", "Category filter should preserve the normalized category value."


def test_list_tickets_filter_priority(client, make_headers, ticket_payload):
    _create_ticket(client, make_headers(request_id="req-ticket-priority-1"), ticket_payload)
    _create_ticket(
        client,
        make_headers(request_id="req-ticket-priority-2"),
        {**ticket_payload, "summary": "Low urgency question", "impact": "low", "urgency": "low"},
    )

    response = client.get("/api/v1/tickets?priority=high", headers=make_headers(request_id="req-ticket-filter-priority"))

    assert response.status_code == 200, "Ticket list filtered by priority should return HTTP 200."
    data = response.json()
    assert len(data) == 1, "Priority filter should return only the matching ticket."
    assert data[0]["priority"] == "high", "Priority filter should preserve the computed priority value."


def test_list_tickets_filter_status(client, db_session, make_headers, ticket_payload):
    first_response = _create_ticket(client, make_headers(request_id="req-ticket-status-1"), ticket_payload)
    second_response = _create_ticket(
        client,
        make_headers(request_id="req-ticket-status-2"),
        {**ticket_payload, "summary": "Closed ticket candidate"},
    )

    open_ticket = db_session.get(Ticket, first_response.json()["ticket_id"])
    closed_ticket = db_session.get(Ticket, second_response.json()["ticket_id"])
    open_ticket.status = "open"
    closed_ticket.status = "closed"
    db_session.commit()

    response = client.get("/api/v1/tickets?status=closed", headers=make_headers(request_id="req-ticket-filter-status"))

    assert response.status_code == 200, "Ticket list filtered by status should return HTTP 200."
    data = response.json()
    assert len(data) == 1, "Status filter should return only the ticket with the requested status."
    assert data[0]["status"] == "closed", "Status filter should return the closed ticket."


def test_list_tickets_student_id_isolation(client, make_headers, ticket_payload):
    _create_ticket(client, make_headers(student_id="student-a", request_id="req-ticket-student-a"), ticket_payload)
    _create_ticket(
        client,
        make_headers(student_id="student-b", request_id="req-ticket-student-b"),
        {**ticket_payload, "summary": "Student B ticket"},
    )

    response = client.get("/api/v1/tickets", headers=make_headers(student_id="student-a", request_id="req-ticket-student-a-list"))

    assert response.status_code == 200, "Ticket list for a student should still return HTTP 200."
    assert len(response.json()) == 1, "Students should only see tickets created under their own X-Student-ID."
    assert response.json()[0]["student_id"] == "student-a", "Ticket isolation should prevent cross-student visibility."


def test_create_ticket_missing_fields(client, make_headers):
    response = client.post(
        "/api/v1/tickets",
        headers=make_headers(request_id="req-ticket-invalid"),
        json={"employee_id": "EMP001", "category": "it"},
    )

    assert response.status_code == 422, "Missing required ticket fields should trigger validation errors."
