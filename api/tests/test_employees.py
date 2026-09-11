EXPECTED_EMPLOYEE_FIELDS = {"id", "name", "department", "email", "role", "vip"}


def test_get_employee_success(client, make_headers):
    response = client.get("/api/v1/employees/EMP001", headers=make_headers())

    assert response.status_code == 200, "Existing employee EMP001 should be returned successfully."

    data = response.json()
    assert data["id"] == "EMP001", "Employee response should preserve the requested employee ID."
    assert data["name"] == "Ayla Mercer", "Seeded employee EMP001 should match the expected name."
    assert data["department"] == "Marketing", "Seeded employee EMP001 should match the expected department."
    assert data["email"] == "ayla.mercer@example.com", "Seeded employee EMP001 should match the expected email."


def test_get_employee_not_found(client, make_headers):
    response = client.get("/api/v1/employees/EMP999", headers=make_headers(request_id="req-missing-employee"))

    assert response.status_code == 404, "Unknown employees should return HTTP 404."
    assert response.json()["detail"] == "Employee not found", "Employee not found response should contain the expected detail."


def test_get_employee_fields(client, make_headers):
    response = client.get("/api/v1/employees/EMP002", headers=make_headers(request_id="req-employee-fields"))

    assert response.status_code == 200, "Employee field validation test should receive HTTP 200."

    data = response.json()
    assert EXPECTED_EMPLOYEE_FIELDS.issubset(data.keys()), "Employee response should contain every expected field."


def test_multiple_employees(client, make_headers):
    for index in range(1, 21):
        employee_id = f"EMP{index:03d}"
        response = client.get(
            f"/api/v1/employees/{employee_id}",
            headers=make_headers(request_id=f"req-{employee_id.lower()}"),
        )
        assert response.status_code == 200, f"Seeded employee {employee_id} should exist in the test database."
        assert response.json()["id"] == employee_id, f"Employee endpoint should return the same ID for {employee_id}."


def test_employee_vip_field(client, make_headers):
    response = client.get("/api/v1/employees/EMP002", headers=make_headers(request_id="req-employee-vip"))

    assert response.status_code == 200, "VIP field test should receive HTTP 200."
    assert isinstance(response.json()["vip"], bool), "Employee VIP flag should always be serialized as a boolean."
