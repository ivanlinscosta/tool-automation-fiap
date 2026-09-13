from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoints_return_expected_payload():
    with TestClient(app) as client:
        root_health_response = client.get("/health")
        api_health_response = client.get("/api/v1/health")

    expected = {"status": "ok", "service": "quantum-commerce-api", "version": "2.0.0"}
    assert root_health_response.status_code == 200
    assert api_health_response.status_code == 200
    assert root_health_response.json() == expected
    assert api_health_response.json() == expected
