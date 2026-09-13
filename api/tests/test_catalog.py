from fastapi.testclient import TestClient

from app.main import app


def _headers(group: str) -> dict[str, str]:
    return {"X-Lab-Group": group}


def test_search_products_by_query_and_filters():
    with TestClient(app) as client:
        notebook_response = client.get(
            "/api/v1/products/search",
            params={"q": "notebook"},
            headers=_headers("test-cat-01"),
        )

        assert notebook_response.status_code == 200
        notebook_data = notebook_response.json()
        assert any(product["sku"] == "QTM-NBK-00123" for product in notebook_data)

        electronics_response = client.get(
            "/api/v1/products/search",
            params={"category": "electronics"},
            headers=_headers("test-cat-01"),
        )

        assert electronics_response.status_code == 200
        electronics_data = electronics_response.json()
        assert len(electronics_data) > 1
        assert all(product["category"] == "electronics" for product in electronics_data)

        brand_response = client.get(
            "/api/v1/products/search",
            params={"brand": "QuantumTech", "max_price": 500},
            headers=_headers("test-cat-01"),
        )

        assert brand_response.status_code == 200
        brand_data = brand_response.json()
        assert brand_data
        assert all(product["brand"] == "QuantumTech" and product["price"] <= 500 for product in brand_data)


def test_search_products_returns_empty_when_no_matches():
    with TestClient(app) as client:
        no_category_response = client.get(
            "/api/v1/products/search",
            params={"category": "nonexistent-category"},
            headers=_headers("test-cat-02"),
        )

        assert no_category_response.status_code == 200
        assert no_category_response.json() == []

        high_price_response = client.get(
            "/api/v1/products/search",
            params={"min_price": 10000},
            headers=_headers("test-cat-02"),
        )

        assert high_price_response.status_code == 200
        assert high_price_response.json() == []


def test_get_product_success():
    with TestClient(app) as client:
        response = client.get("/api/v1/products/QTM-NBK-00123", headers=_headers("test-cat-03"))

    assert response.status_code == 200
    assert response.json() == {
        "sku": "QTM-NBK-00123",
        "name": "Notebook QuantumBook Pro 14",
        "category": "electronics",
        "subcategory": "notebooks",
        "brand": "QuantumTech",
        "price": 7499.9,
        "currency": "BRL",
        "active": True,
        "rating": 4.7,
    }


def test_get_product_not_found():
    with TestClient(app) as client:
        response = client.get("/api/v1/products/QTM-UNKNOWN-99999", headers=_headers("test-cat-04"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_get_catalog_stats_for_seeded_database():
    with TestClient(app) as client:
        response = client.get("/api/v1/catalog/stats", headers=_headers("test-cat-05"))

    assert response.status_code == 200
    assert response.json() == {
        "total_skus": 171,
        "active_skus": 170,
        "categories": 9,
        "countries": 6,
    }
