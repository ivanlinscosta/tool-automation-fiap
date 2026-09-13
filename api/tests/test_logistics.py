from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-logistics-01"


def _headers() -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP}


def test_get_shipment_by_id_returns_seeded_shipment() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/shipments/SHP-87421", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "ORD-2026-10001"
    assert data["shipment_id"] == "SHP-87421"
    assert data["carrier"] == "Quantum Logistics"
    assert data["status"] == "in_transit"
    assert data["tracking_code"] == "QTM982734BR"
    assert data["estimated_delivery"] == "2026-09-14"
    assert len(data["events"]) >= 3
    assert all("status" in event and "timestamp" in event for event in data["events"])


def test_get_shipment_by_id_returns_404_for_unknown_shipment() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/shipments/SHP-99999", headers=_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Shipment not found"}
