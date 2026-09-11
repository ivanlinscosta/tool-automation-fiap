def test_list_students(client, make_headers):
    response = client.get("/api/v1/students", headers=make_headers())

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 20
    assert data[0]["id"].startswith("STU")


def test_get_student_success(client, make_headers):
    response = client.get("/api/v1/students/STU001", headers=make_headers(request_id="req-student-1"))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "STU001"
    assert data["email"] == "stu001@fiap.lab"


def test_get_student_not_found(client, make_headers):
    response = client.get("/api/v1/students/STU999", headers=make_headers(request_id="req-student-missing"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"
