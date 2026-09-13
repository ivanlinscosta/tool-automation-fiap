import pytest
from fastapi.testclient import TestClient

from app.main import app


def _headers(group: str) -> dict[str, str]:
    return {"X-Lab-Group": group}


def test_search_customers_by_name_and_without_filters():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/customers/search",
            params={"name": "Ana"},
            headers=_headers("test-cust-01"),
        )

        assert response.status_code == 200
        data = response.json()
        assert any(customer["id"] == "CUS-1039" and customer["name"] == "Ana Oliveira" for customer in data)
        assert all("ana" in customer["name"].lower() for customer in data)

        empty_response = client.get("/api/v1/customers/search", headers=_headers("test-cust-01"))

        assert empty_response.status_code == 200
        all_customers = empty_response.json()
        assert 1 <= len(all_customers) <= 100


def test_get_customer_by_id_success():
    with TestClient(app) as client:
        response = client.get("/api/v1/customers/CUS-1001", headers=_headers("test-cust-02"))

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "id": "CUS-1001",
        "name": "Marina Oliveira",
        "email": "marina.oliveira@example.com",
        "country": "BR",
        "city": "São Paulo",
        "segment": "premium",
        "loyalty_tier": "gold",
        "customer_since": "2021-03-12",
        "lifetime_value": 18450.9,
        "preferred_channel": "whatsapp",
    }


def test_get_customer_by_id_not_found():
    with TestClient(app) as client:
        response = client.get("/api/v1/customers/CUS-9999", headers=_headers("test-cust-03"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_get_customer_context_for_seeded_customer():
    with TestClient(app) as client:
        response = client.get("/api/v1/customers/CUS-1001/context", headers=_headers("test-cust-04"))

    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "CUS-1001"
    assert data["segment"] == "premium"
    assert data["loyalty_tier"] == "gold"
    assert data["total_orders"] == 47
    assert data["open_orders"] >= 0
    assert data["open_support_cases"] >= 0
    assert data["returns_last_12_months"] >= 0
    assert data["lifetime_value"] == 18450.9


def test_get_customer_context_not_found():
    with TestClient(app) as client:
        response = client.get("/api/v1/customers/CUS-9999/context", headers=_headers("test-cust-05"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_get_customer_orders_and_status_filter():
    with TestClient(app) as client:
        response = client.get("/api/v1/customers/CUS-1001/orders", headers=_headers("test-cust-06"))

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        assert [order["id"] for order in data] == [
            "ORD-2026-10057",
            "ORD-2026-10014",
            "ORD-2026-10001",
            "ORD-2026-10005",
            "ORD-2026-10007",
        ]

        order_10001 = next(order for order in data if order["id"] == "ORD-2026-10001")
        assert order_10001["customer_id"] == "CUS-1001"
        assert order_10001["status"] == "in_transit"
        assert order_10001["items"]
        assert {item["sku"] for item in order_10001["items"]} == {"QTM-NBK-00123", "QTM-ACC-00017"}

        delivered_response = client.get(
            "/api/v1/customers/CUS-1001/orders",
            params={"status": "delivered"},
            headers=_headers("test-cust-06"),
        )

        assert delivered_response.status_code == 200
        delivered_orders = delivered_response.json()
        assert [order["id"] for order in delivered_orders] == [
            "ORD-2026-10057",
            "ORD-2026-10005",
            "ORD-2026-10007",
        ]
        assert all(order["status"] == "delivered" for order in delivered_orders)


def test_get_customer_orders_not_found():
    with TestClient(app) as client:
        response = client.get("/api/v1/customers/CUS-9999/orders", headers=_headers("test-cust-07"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_get_customer_recommendation_context():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/customers/CUS-1001/recommendation-context",
            headers=_headers("test-cust-08"),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "CUS-1001"
    assert "electronics" in data["recent_categories"]
    assert data["recent_products"] == [
        "QTM-SNR-01070",
        "QTM-HRC-01134",
        "QTM-SNR-01067",
        "QTM-LMP-01051",
        "QTM-COF-01102",
    ]
    assert data["preferred_brands"] == ["QuantumHome", "QuantumTech", "QuantumWear"]
    assert data["average_order_value"] == pytest.approx(3665.358)
    assert data["price_sensitivity"] == "low"


def test_get_customer_recommendation_context_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/customers/CUS-9999/recommendation-context",
            headers=_headers("test-cust-09"),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"
