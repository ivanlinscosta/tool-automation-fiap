def test_list_departments(client, make_headers):
    response = client.get("/api/v1/departments", headers=make_headers())

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 9
    assert any(item["category"] == "academic_services" for item in data)


def test_get_department_success(client, make_headers):
    response = client.get("/api/v1/departments/campus_access", headers=make_headers(request_id="req-dept-campus"))

    assert response.status_code == 200
    data = response.json()
    assert data["department"] == "Campus Access"
    assert data["queue"] == "campus-access"


def test_get_department_not_found(client, make_headers):
    response = client.get("/api/v1/departments/unknown", headers=make_headers(request_id="req-dept-missing"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Department not found"
