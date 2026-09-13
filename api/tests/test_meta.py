from fastapi.testclient import TestClient

from app.main import app


def _headers(lab_group: str | None = None, request_id: str = "req-001", idem_key: str | None = None) -> dict[str, str]:
    headers = {"X-Request-ID": request_id}
    if lab_group is not None:
        headers["X-Lab-Group"] = lab_group
    if idem_key is not None:
        headers["Idempotency-Key"] = idem_key
    return headers


def test_root_endpoint_returns_service_metadata():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Quantum Commerce API",
        "version": "2.0.0",
        "docs": "/docs",
        "api_base": "/api/v1",
    }


def test_meta_endpoint_reports_seed_counts_and_links():
    with TestClient(app) as client:
        response = client.get("/api/v1/meta", headers=_headers("test-meta", "req-meta"))

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Quantum Commerce API"
    assert body["version"] == "2.0.0"
    assert body["api_base"] == "/api/v1"
    assert body["docs"] == "/docs"
    assert body["health"] == "/api/v1/health"
    assert body["openapi"] == "/openapi.json"
    assert body["environment"] == "development"
    assert body["seed_today"] == "2026-09-13"
    assert body["seeded_entities"] == {
        "customers": 50,
        "products": 171,
        "orders": 91,
        "shipments": 77,
        "policies": 20,
        "support_cases": 20,
        "return_records": 15,
        "approvals": 10,
        "refunds": 2,
        "promotions": 6,
        "interactions": 12,
        "events": 5,
    }
    assert "/api/v1/lab/slow" in body["lab_endpoints"]


def test_idempotency_replays_support_case_conflicts_across_resource_types_and_meta_counts_all_rows():
    support_payload = {
        "customer_id": "CUS-1001",
        "category": "delivery",
        "summary": "Need help with delayed order",
        "description": "The package is still delayed after the expected date.",
    }
    approval_payload = {
        "type": "refund",
        "reference_id": "ORD-2026-10001",
        "requested_by": "ai-agent",
        "amount": 7499.90,
        "reason": "Refund requested after delivery issue",
    }

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/support/cases",
            headers=_headers("test-meta-idem", "req-meta-idem-create", "k1"),
            json=support_payload,
        )

        assert create_response.status_code == 201
        created_case = create_response.json()
        assert created_case["case_id"] == "CASE-2026-10021"

        replay_response = client.post(
            "/api/v1/support/cases",
            headers=_headers("test-meta-idem", "req-meta-idem-replay", "k1"),
            json=support_payload,
        )

        assert replay_response.status_code == 200
        assert replay_response.json() == created_case

        conflict_response = client.post(
            "/api/v1/approvals",
            headers=_headers("test-meta-idem", "req-meta-idem-conflict", "k1"),
            json=approval_payload,
        )

        assert conflict_response.status_code == 409
        assert "Idempotency-Key 'k1' was already used for support_case" in conflict_response.json()["detail"]

        meta_response = client.get(
            "/api/v1/meta",
            headers=_headers("test-meta-idem", "req-meta-idem-meta"),
        )

    assert meta_response.status_code == 200
    assert meta_response.json()["seeded_entities"]["support_cases"] == 21
