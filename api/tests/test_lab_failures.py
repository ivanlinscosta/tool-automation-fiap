import time


def test_lab_slow(client, make_headers):
    start = time.perf_counter()
    response = client.get("/api/v1/lab/slow?seconds=2", headers=make_headers())
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert 1.75 <= elapsed < 3.5
    assert response.json()["seconds"] == 2


def test_lab_error(client, make_headers):
    response = client.get("/api/v1/lab/error", headers=make_headers(request_id="req-lab-error"))

    assert response.status_code == 500
    assert response.json()["detail"] == "Simulated internal server error"


def test_lab_not_found(client, make_headers):
    response = client.get("/api/v1/lab/not-found", headers=make_headers(request_id="req-lab-not-found"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found (simulated)"


def test_lab_rate_limit_first_3(client, make_headers):
    for count in range(1, 4):
        response = client.get("/api/v1/lab/rate-limit", headers=make_headers(student_id="rate-limit-student", request_id=f"req-rate-limit-{count}"))
        assert response.status_code == 200
        assert response.json()["requests_in_window"] == count


def test_lab_rate_limit_429(client, make_headers):
    for count in range(1, 4):
        response = client.get("/api/v1/lab/rate-limit", headers=make_headers(student_id="rate-limit-overflow", request_id=f"req-rate-limit-ok-{count}"))
        assert response.status_code == 200

    overflow_response = client.get("/api/v1/lab/rate-limit", headers=make_headers(student_id="rate-limit-overflow", request_id="req-rate-limit-overflow"))

    assert overflow_response.status_code == 429
    assert overflow_response.headers["Retry-After"] == "10"
    assert overflow_response.json()["detail"] == "Too many requests"


def test_lab_validation_valid(client, make_headers):
    response = client.post(
        "/api/v1/lab/validation",
        headers=make_headers(request_id="req-lab-validation-valid"),
        json={"email": "student@fiap.lab", "amount": 42.5},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "student@fiap.lab"
    assert data["amount"] == 42.5


def test_lab_validation_invalid_email(client, make_headers):
    response = client.post(
        "/api/v1/lab/validation",
        headers=make_headers(request_id="req-lab-validation-email"),
        json={"email": "not-an-email", "amount": 10},
    )

    assert response.status_code == 422


def test_lab_validation_negative_amount(client, make_headers):
    response = client.post(
        "/api/v1/lab/validation",
        headers=make_headers(request_id="req-lab-validation-amount"),
        json={"email": "student@fiap.lab", "amount": -1},
    )

    assert response.status_code == 422
