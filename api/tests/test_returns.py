from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-returns-01"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


def test_check_return_eligibility_for_delivered_orders_and_missing_order() -> None:
    with TestClient(app) as client:
        eligible_response = client.post(
            "/api/v1/returns/check-eligibility",
            headers=_headers(),
            json={"order_id": "ORD-2026-10005", "sku": "QTM-AUD-01023"},
        )
        outside_window_response = client.post(
            "/api/v1/returns/check-eligibility",
            headers=_headers(),
            json={"order_id": "ORD-2026-10007", "sku": "QTM-BED-01089"},
        )
        unknown_order_response = client.post(
            "/api/v1/returns/check-eligibility",
            headers=_headers(),
            json={"order_id": "ORD-2026-99999", "sku": "QTM-AUD-01023"},
        )

    assert eligible_response.status_code == 200
    assert eligible_response.json() == {
        "eligible": True,
        "reason": "within_return_window",
        "days_since_delivery": 12,
        "return_window_days": 30,
        "policy_id": "POL-RETURN-001",
    }

    assert outside_window_response.status_code == 200
    assert outside_window_response.json() == {
        "eligible": False,
        "reason": "outside_return_window",
        "days_since_delivery": 50,
        "return_window_days": 30,
        "policy_id": None,
    }

    assert unknown_order_response.status_code == 200
    assert unknown_order_response.json() == {
        "eligible": False,
        "reason": "order_not_found",
        "days_since_delivery": None,
        "return_window_days": 0,
        "policy_id": None,
    }


def test_check_return_eligibility_rejects_not_delivered_order_and_missing_sku() -> None:
    with TestClient(app) as client:
        not_delivered_response = client.post(
            "/api/v1/returns/check-eligibility",
            headers=_headers(),
            json={"order_id": "ORD-2026-10001", "sku": "QTM-NBK-00123"},
        )
        wrong_sku_response = client.post(
            "/api/v1/returns/check-eligibility",
            headers=_headers(),
            json={"order_id": "ORD-2026-10005", "sku": "QTM-NBK-00123"},
        )

    assert not_delivered_response.status_code == 200
    assert not_delivered_response.json() == {
        "eligible": False,
        "reason": "order_not_delivered",
        "days_since_delivery": None,
        "return_window_days": 30,
        "policy_id": None,
    }

    assert wrong_sku_response.status_code == 200
    assert wrong_sku_response.json() == {
        "eligible": False,
        "reason": "product_not_in_order",
        "days_since_delivery": None,
        "return_window_days": 30,
        "policy_id": None,
    }


def test_create_return_assigns_next_seeded_identifier() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/returns",
            headers=_headers(),
            json={
                "customer_id": "CUS-1001",
                "order_id": "ORD-2026-10005",
                "sku": "QTM-AUD-01023",
                "reason": "Produto incompatível com minha necessidade",
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "return_id": "RET-90016",
        "status": "requested",
        "protocol": "QRET-2026-90016",
    }


def test_create_return_replays_idempotent_requests_and_rejects_cross_resource_key_reuse() -> None:
    payload = {
        "customer_id": "CUS-1001",
        "order_id": "ORD-2026-10005",
        "sku": "QTM-AUD-01023",
        "reason": "Arrependimento da compra",
    }

    with TestClient(app) as client:
        first_response = client.post(
            "/api/v1/returns",
            headers=_headers(**{"Idempotency-Key": "idem-ret-replay"}),
            json=payload,
        )
        replay_response = client.post(
            "/api/v1/returns",
            headers=_headers(**{"Idempotency-Key": "idem-ret-replay"}),
            json=payload,
        )
        support_case_response = client.post(
            "/api/v1/support/cases",
            headers=_headers(**{"Idempotency-Key": "idem-ret-conflict"}),
            json={
                "customer_id": "CUS-1001",
                "category": "return",
                "summary": "Need help with a return",
                "description": "Creating a support case to reserve the idempotency key.",
            },
        )
        conflict_response = client.post(
            "/api/v1/returns",
            headers=_headers(**{"Idempotency-Key": "idem-ret-conflict"}),
            json=payload,
        )

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    assert replay_response.json() == first_response.json()

    assert support_case_response.status_code == 201
    assert conflict_response.status_code == 409
    assert "support_case" in conflict_response.json()["detail"]


def test_create_return_validates_required_fields_and_unknown_orders() -> None:
    with TestClient(app) as client:
        validation_response = client.post(
            "/api/v1/returns",
            headers=_headers(),
            json={
                "order_id": "ORD-2026-10005",
                "sku": "QTM-AUD-01023",
                "reason": "Arrependimento da compra",
            },
        )
        unknown_order_response = client.post(
            "/api/v1/returns",
            headers=_headers(),
            json={
                "customer_id": "CUS-1001",
                "order_id": "ORD-2026-99999",
                "sku": "QTM-AUD-01023",
                "reason": "Arrependimento da compra",
            },
        )

    assert validation_response.status_code == 422
    assert unknown_order_response.status_code == 404
    assert unknown_order_response.json() == {"detail": "Order not found"}


def test_get_return_by_id_reads_seeded_records_and_404s_for_unknown_return() -> None:
    with TestClient(app) as client:
        first_response = client.get("/api/v1/returns/RET-90001", headers=_headers())
        second_response = client.get("/api/v1/returns/RET-90002", headers=_headers())
        missing_response = client.get("/api/v1/returns/RET-99999", headers=_headers())

    assert first_response.status_code == 200
    first_data = first_response.json()
    assert first_data["return_id"] == "RET-90001"
    assert first_data["protocol"] == "QRET-2026-90001"
    assert first_data["customer_id"] == "CUS-1001"
    assert first_data["order_id"] == "ORD-2026-10005"
    assert first_data["sku"] == "QTM-AUD-01023"
    assert first_data["status"] == "requested"
    assert first_data["lab_group"] == "system"
    assert first_data["created_at"].startswith("2026-09-03T14:00:00")

    assert second_response.status_code == 200
    second_data = second_response.json()
    assert second_data["return_id"] == "RET-90002"
    assert second_data["status"] == "rejected"

    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Return not found"}


def test_list_customer_returns_includes_seeded_returns_and_unknown_customer_is_empty() -> None:
    with TestClient(app) as client:
        customer_response = client.get("/api/v1/customers/CUS-1001/returns", headers=_headers())
        unknown_customer_response = client.get("/api/v1/customers/CUS-99999/returns", headers=_headers())

    assert customer_response.status_code == 200
    return_ids = {return_record["return_id"] for return_record in customer_response.json()}
    assert {"RET-90001", "RET-90002"}.issubset(return_ids)

    assert unknown_customer_response.status_code == 200
    assert unknown_customer_response.json() == []
