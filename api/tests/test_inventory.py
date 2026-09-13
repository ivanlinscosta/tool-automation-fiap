from fastapi.testclient import TestClient

from app.main import app


def _headers(group: str) -> dict[str, str]:
    return {"X-Lab-Group": group}


def test_get_inventory_by_sku_success():
    with TestClient(app) as client:
        response = client.get("/api/v1/inventory/QTM-NBK-00123", headers=_headers("test-inv-01"))

    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "QTM-NBK-00123"
    assert data["total_available"] == 37
    warehouses = {warehouse["warehouse_id"]: warehouse for warehouse in data["warehouses"]}
    assert warehouses["BR-SP-01"] == {
        "warehouse_id": "BR-SP-01",
        "city": "São Paulo",
        "available": 21,
        "reserved": 4,
    }
    assert warehouses["BR-RJ-01"] == {
        "warehouse_id": "BR-RJ-01",
        "city": "Rio de Janeiro",
        "available": 16,
        "reserved": 2,
    }
    assert sum(warehouse["available"] for warehouse in data["warehouses"]) == data["total_available"]


def test_get_inventory_not_found_for_unknown_product():
    with TestClient(app) as client:
        response = client.get("/api/v1/inventory/QTM-UNKNOWN-99999", headers=_headers("test-inv-02"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_get_inventory_not_found_when_product_has_no_inventory_rows():
    with TestClient(app) as client:
        response = client.get("/api/v1/inventory/QTM-NBK-00150", headers=_headers("test-inv-03"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Inventory not found"


def test_get_inventory_availability_by_postal_code():
    with TestClient(app) as client:
        sp_response = client.get(
            "/api/v1/inventory/QTM-NBK-00123/availability",
            params={"postal_code": "01310-100"},
            headers=_headers("test-inv-04"),
        )

        assert sp_response.status_code == 200
        assert sp_response.json() == {
            "sku": "QTM-NBK-00123",
            "available": True,
            "quantity": 21,
            "estimated_delivery_days": 2,
        }

        rj_response = client.get(
            "/api/v1/inventory/QTM-NBK-00123/availability",
            params={"postal_code": "22000-000"},
            headers=_headers("test-inv-04"),
        )

        assert rj_response.status_code == 200
        assert rj_response.json() == {
            "sku": "QTM-NBK-00123",
            "available": True,
            "quantity": 16,
            "estimated_delivery_days": 3,
        }

        empty_inventory_response = client.get(
            "/api/v1/inventory/QTM-NBK-00150/availability",
            params={"postal_code": "01310-100"},
            headers=_headers("test-inv-04"),
        )

        assert empty_inventory_response.status_code == 200
        assert empty_inventory_response.json() == {
            "sku": "QTM-NBK-00150",
            "available": False,
            "quantity": 0,
            "estimated_delivery_days": 2,
        }


def test_get_inventory_availability_validation_and_not_found():
    with TestClient(app) as client:
        missing_postal_response = client.get(
            "/api/v1/inventory/QTM-NBK-00123/availability",
            headers=_headers("test-inv-05"),
        )

        assert missing_postal_response.status_code == 422
        detail = missing_postal_response.json()["detail"]
        assert any(item["loc"] == ["query", "postal_code"] for item in detail)

        unknown_sku_response = client.get(
            "/api/v1/inventory/QTM-UNKNOWN-99999/availability",
            params={"postal_code": "01310-100"},
            headers=_headers("test-inv-05"),
        )

        assert unknown_sku_response.status_code == 404
        assert unknown_sku_response.json()["detail"] == "Product not found"
