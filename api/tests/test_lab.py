import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _headers(lab_group: str | None = None, request_id: str = "req-001") -> dict[str, str]:
    headers = {"X-Request-ID": request_id}
    if lab_group is not None:
        headers["X-Lab-Group"] = lab_group
    return headers


def test_lab_slow_waits_about_one_second_and_returns_seconds_value():
    with TestClient(app) as client:
        start = time.perf_counter()
        response = client.get(
            "/api/v1/lab/slow?seconds=1",
            headers=_headers("test-lab-slow", "req-lab-slow"),
        )
        elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert 0.9 <= elapsed < 3.0
    assert response.json() == {"message": "Response after 1 seconds", "seconds": 1}


def test_lab_error_returns_500_and_creates_audit_event():
    with TestClient(app, raise_server_exceptions=False) as client:
        error_response = client.get(
            "/api/v1/lab/error",
            headers=_headers("test-lab-error", "req-lab-error"),
        )

        assert error_response.status_code == 500
        assert error_response.json()["detail"] == "Simulated internal server error"

        events_response = client.get(
            "/api/v1/events?type=lab_error_triggered",
            headers=_headers("test-lab-error", "req-lab-error-events"),
        )

        assert events_response.status_code == 200
        events = events_response.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "lab_error_triggered"
        assert events[0]["lab_group"] == "test-lab-error"
        assert events[0]["resource_type"] == "lab_failure"
        assert events[0]["resource_id"] == "req-lab-error"


def test_lab_rate_limit_returns_429_on_fourth_request_for_same_group():
    lab_group = f"test-lab-rate-{uuid4().hex}"

    with TestClient(app) as client:
        for expected_count in (1, 2, 3):
            response = client.get(
                "/api/v1/lab/rate-limit",
                headers=_headers(lab_group, f"req-lab-rate-{expected_count}"),
            )

            assert response.status_code == 200
            assert response.json()["requests_in_window"] == expected_count
            assert response.json()["lab_group"] == lab_group

        fourth_response = client.get(
            "/api/v1/lab/rate-limit",
            headers=_headers(lab_group, "req-lab-rate-4"),
        )

    assert fourth_response.status_code == 429
    assert fourth_response.headers["Retry-After"] == "10"
    assert fourth_response.json() == {"detail": "Too many requests", "retry_after_seconds": 10}


def test_lab_not_found_returns_expected_payload():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/lab/not-found",
            headers=_headers("test-lab-404", "req-lab-not-found"),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found (simulated)"


def test_lab_validation_accepts_valid_payload():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lab/validation",
            headers=_headers("test-lab-validation", "req-lab-validation-ok"),
            json={"email": "buyer@quantum.example", "amount": 42.5},
        )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Validation passed",
        "email": "buyer@quantum.example",
        "amount": 42.5,
    }


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        ({"email": "not-an-email", "amount": 42.5}, "email"),
        ({"email": "buyer@quantum.example", "amount": -1}, "amount"),
    ],
)
def test_lab_validation_rejects_invalid_payloads(payload: dict[str, object], expected_fragment: str):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lab/validation",
            headers=_headers("test-lab-validation", "req-lab-validation-invalid"),
            json=payload,
        )

    assert response.status_code == 422
    assert any(expected_fragment in ".".join(str(part) for part in item["loc"]) for item in response.json()["detail"])
