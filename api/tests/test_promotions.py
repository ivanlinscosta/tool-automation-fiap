from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-promotions-01"


def _headers() -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP}


def test_list_active_promotions_and_country_filter():
    with TestClient(app) as client:
        response = client.get("/api/v1/promotions", headers=_headers())
        filtered = client.get("/api/v1/promotions?country=BR", headers=_headers())

    expected_ids = ["PROMO-101", "PROMO-104", "PROMO-102", "PROMO-103", "PROMO-100", "PROMO-105"]

    assert response.status_code == 200
    data = response.json()
    assert [item["promotion_id"] for item in data] == expected_ids
    assert len(data) == 6
    assert all(item["active"] is True for item in data)

    assert filtered.status_code == 200
    filtered_data = filtered.json()
    assert [item["promotion_id"] for item in filtered_data] == expected_ids
    assert all(item["country"] == "BR" for item in filtered_data)


def test_get_eligible_promotions_for_customer_without_sku_marks_product_rules_as_unmet():
    with TestClient(app) as client:
        response = client.get("/api/v1/promotions/eligible?customer_id=CUS-1001", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    by_id = {item["promotion_id"]: item for item in data}
    assert len(data) == 6
    assert by_id["PROMO-101"] == {
        "promotion_id": "PROMO-101",
        "name": "Quantum Fashion Friday",
        "discount_pct": 20.0,
        "eligible": False,
        "reason": "sku_required_for_product_rules",
    }
    assert by_id["PROMO-104"] == {
        "promotion_id": "PROMO-104",
        "name": "Beauty Essentials",
        "discount_pct": 18.0,
        "eligible": False,
        "reason": "sku_required_for_product_rules",
    }
    assert all(item["eligible"] is False for item in data)
    assert all(item["reason"] == "sku_required_for_product_rules" for item in data)


def test_get_eligible_promotions_with_customer_and_sku_resolves_matches_and_mismatches():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/promotions/eligible?customer_id=CUS-1001&sku=QTM-NBK-00123",
            headers=_headers(),
        )

    assert response.status_code == 200
    by_id = {item["promotion_id"]: item for item in response.json()}
    assert by_id["PROMO-100"]["eligible"] is True
    assert by_id["PROMO-100"]["reason"] == "eligible"
    assert by_id["PROMO-101"]["eligible"] is False
    assert by_id["PROMO-101"]["reason"] == "category_mismatch"
    assert by_id["PROMO-104"]["eligible"] is False
    assert by_id["PROMO-104"]["reason"] == "category_mismatch"
    assert by_id["PROMO-105"]["eligible"] is True
    assert by_id["PROMO-105"]["reason"] == "eligible"


def test_get_eligible_promotions_requires_customer_or_sku():
    with TestClient(app) as client:
        response = client.get("/api/v1/promotions/eligible", headers=_headers())

    assert response.status_code == 422
    assert response.json()["detail"] == "At least one of customer_id or sku is required"


def test_get_promotion_by_id_and_unknown_id():
    with TestClient(app) as client:
        response = client.get("/api/v1/promotions/PROMO-101", headers=_headers())
        unknown = client.get("/api/v1/promotions/PROMO-999", headers=_headers())

    assert response.status_code == 200
    assert response.json() == {
        "promotion_id": "PROMO-101",
        "name": "Quantum Fashion Friday",
        "description": "20% off em moda selecionada.",
        "discount_pct": 20.0,
        "category": "fashion",
        "brand": None,
        "country": "BR",
        "min_price": None,
        "active": True,
        "starts_at": "2026-09-10",
        "ends_at": "2026-10-05",
    }
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Promotion not found"
