import pytest
from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-orders-01"


def _headers() -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP}


def test_get_order_by_id_returns_seeded_order_details() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/orders/ORD-2026-10001", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "ORD-2026-10001"
    assert data["customer_id"] == "CUS-1001"
    assert data["status"] == "in_transit"
    assert data["created_at"].startswith("2026-09-02T13:42:00")
    assert data["total"] == pytest.approx(7899.80)
    assert data["currency"] == "BRL"
    assert any(
        item == {
            "sku": "QTM-NBK-00123",
            "name": "Notebook QuantumBook Pro 14",
            "quantity": 1,
            "unit_price": 7499.9,
        }
        for item in data["items"]
    )


def test_get_order_by_id_returns_404_for_unknown_order() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/orders/ORD-2026-99999", headers=_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_get_order_shipment_returns_seeded_shipment_details() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/orders/ORD-2026-10001/shipment", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-2026-10001"
    assert data["shipment_id"] == "SHP-87421"
    assert data["carrier"] == "Quantum Logistics"
    assert data["tracking_code"] == "QTM982734BR"
    assert data["status"] == "in_transit"
    assert data["estimated_delivery"] == "2026-09-14"
    assert len(data["events"]) >= 3
    assert all("status" in event and "timestamp" in event for event in data["events"])


def test_get_order_shipment_returns_404_for_unknown_order() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/orders/ORD-2026-99999/shipment", headers=_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_get_order_shipment_returns_404_when_existing_order_has_no_shipment() -> None:
    with TestClient(app) as client:
        order_response = client.get("/api/v1/orders/ORD-2026-10031", headers=_headers())
        shipment_response = client.get("/api/v1/orders/ORD-2026-10031/shipment", headers=_headers())

    assert order_response.status_code == 200
    assert shipment_response.status_code == 404
    assert shipment_response.json() == {"detail": "Shipment not found"}
