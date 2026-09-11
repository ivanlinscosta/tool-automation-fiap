import time

import pytest


def test_lab_slow(client, make_headers):
    start = time.perf_counter()
    response = client.get("/api/v1/lab/slow?seconds=2", headers=make_headers())
    elapsed = time.perf_counter() - start

    assert response.status_code == 200, "Slow endpoint should still return HTTP 200 for valid delays."
    assert 1.75 <= elapsed < 3.5, f"Slow endpoint should delay close to 2 seconds, got {elapsed:.2f}s."
    assert response.json()["seconds"] == 2, "Slow endpoint should echo the requested delay in seconds."


@pytest.mark.xfail(reason="Application validates seconds instead of clamping values above 15.", strict=False)
def test_lab_slow_max_limit(client, make_headers):
    response = client.get("/api/v1/lab/slow?seconds=20", headers=make_headers(request_id="req-lab-slow-max"))

    assert response.status_code == 200, "Slow endpoint should clamp high values instead of rejecting them."
    assert response.json()["seconds"] == 15, "Slow endpoint should clamp seconds above 15 down to 15."


@pytest.mark.xfail(reason="Application validates seconds instead of clamping values below 1.", strict=False)
def test_lab_slow_min_limit(client, make_headers):
    response = client.get("/api/v1/lab/slow?seconds=0", headers=make_headers(request_id="req-lab-slow-min"))

    assert response.status_code == 200, "Slow endpoint should clamp low values instead of rejecting them."
    assert response.json()["seconds"] == 1, "Slow endpoint should clamp seconds below 1 up to 1."


def test_lab_error(client, make_headers):
    response = client.get("/api/v1/lab/error", headers=make_headers(request_id="req-lab-error"))

    assert response.status_code == 500, "Error simulation endpoint should return HTTP 500."
    assert response.json()["detail"] == "Simulated internal server error", "Error simulation endpoint should return the expected error detail."


def test_lab_not_found(client, make_headers):
    response = client.get("/api/v1/lab/not-found", headers=make_headers(request_id="req-lab-not-found"))

    assert response.status_code == 404, "Not-found simulation endpoint should return HTTP 404."
    assert response.json()["detail"] == "Resource not found (simulated)", "Not-found simulation endpoint should return the expected error detail."


def test_lab_rate_limit_first_3(client, make_headers):
    for count in range(1, 4):
        response = client.get(
            "/api/v1/lab/rate-limit",
            headers=make_headers(student_id="rate-limit-student", request_id=f"req-rate-limit-{count}"),
        )
        assert response.status_code == 200, f"Rate-limit endpoint request #{count} should succeed inside the allowed window."
        assert response.json()["requests_in_window"] == count, f"Request #{count} should increment the in-window request counter."


def test_lab_rate_limit_429(client, make_headers):
    for count in range(1, 4):
        response = client.get(
            "/api/v1/lab/rate-limit",
            headers=make_headers(student_id="rate-limit-overflow", request_id=f"req-rate-limit-ok-{count}"),
        )
        assert response.status_code == 200, f"Warm-up rate-limit request #{count} should succeed before the overflow request."

    overflow_response = client.get(
        "/api/v1/lab/rate-limit",
        headers=make_headers(student_id="rate-limit-overflow", request_id="req-rate-limit-overflow"),
    )

    assert overflow_response.status_code == 429, "The fourth rate-limit request in the same window should return HTTP 429."
    assert overflow_response.headers["Retry-After"] == "10", "Rate-limit overflow responses should include the Retry-After header."
    assert overflow_response.json()["detail"] == "Too many requests", "Rate-limit overflow should return the expected error detail."


def test_lab_validation_valid(client, make_headers):
    response = client.post(
        "/api/v1/lab/validation",
        headers=make_headers(request_id="req-lab-validation-valid"),
        json={"email": "student@flowdesk.lab", "amount": 42.5},
    )

    assert response.status_code == 200, "Validation endpoint should accept a valid email and non-negative amount."
    data = response.json()
    assert data["email"] == "student@flowdesk.lab", "Validation endpoint should echo the validated email."
    assert data["amount"] == 42.5, "Validation endpoint should echo the validated amount."


def test_lab_validation_invalid_email(client, make_headers):
    response = client.post(
        "/api/v1/lab/validation",
        headers=make_headers(request_id="req-lab-validation-email"),
        json={"email": "not-an-email", "amount": 10},
    )

    assert response.status_code == 422, "Validation endpoint should reject invalid email addresses."


def test_lab_validation_negative_amount(client, make_headers):
    response = client.post(
        "/api/v1/lab/validation",
        headers=make_headers(request_id="req-lab-validation-amount"),
        json={"email": "student@flowdesk.lab", "amount": -1},
    )

    assert response.status_code == 422, "Validation endpoint should reject negative amount values."
