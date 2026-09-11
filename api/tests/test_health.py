def test_health_check(client, make_headers):
    response = client.get("/health", headers=make_headers())

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "fiap-student-desk-lab-api"
    assert data["version"] == "1.0.0"


def test_root_endpoint(client, make_headers):
    response = client.get("/", headers=make_headers(request_id="req-root"))

    assert response.status_code == 200

    data = response.json()
    assert data["service"] == "FIAP Student Desk Lab API"
    assert data["docs"] == "/docs"
    assert data["openapi"] == "/openapi.json"
    assert data["health"] == "/health"
