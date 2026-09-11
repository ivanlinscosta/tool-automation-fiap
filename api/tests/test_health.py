def test_health_check(client, make_headers):
    response = client.get("/health", headers=make_headers())

    assert response.status_code == 200, "Health endpoint should return HTTP 200."

    data = response.json()
    assert data["status"] == "ok", "Health endpoint should report status='ok'."
    assert data["service"] == "flowdesk-lab-api", "Health endpoint should return the service identifier."
    assert data["version"] == "1.0.0", "Health endpoint should expose the current API version."


def test_root_endpoint(client, make_headers):
    response = client.get("/", headers=make_headers(request_id="req-root"))

    assert response.status_code == 200, "Root endpoint should return HTTP 200."

    data = response.json()
    assert data["service"] == "FlowDesk Lab API", "Root endpoint should return the human-readable service name."
    assert data["docs"] == "/docs", "Root endpoint should expose the docs URL."
    assert data["openapi"] == "/openapi.json", "Root endpoint should expose the OpenAPI URL."
    assert data["health"] == "/health", "Root endpoint should expose the health URL."
