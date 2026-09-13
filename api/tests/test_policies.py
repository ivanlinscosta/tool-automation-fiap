from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-policies-01"


def _headers() -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP}


def test_list_policies_filters_return_policies() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/policies?category=returns", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(
        policy["id"] == "POL-RETURN-001"
        and policy["title"] == "Política de devolução padrão"
        and policy["country"] == "BR"
        and policy["effective_from"] == "2026-01-01"
        for policy in data
    )


def test_list_policies_without_filters_and_with_cancellation_filter() -> None:
    with TestClient(app) as client:
        all_response = client.get("/api/v1/policies", headers=_headers())
        cancellation_response = client.get("/api/v1/policies?category=cancellation", headers=_headers())

    assert all_response.status_code == 200
    assert len(all_response.json()) >= 20

    assert cancellation_response.status_code == 200
    assert any(policy["id"] == "POL-CANCEL-001" for policy in cancellation_response.json())


def test_policy_search_route_is_not_shadowed_by_policy_id_route() -> None:
    with TestClient(app) as client:
        search_response = client.get("/api/v1/policies/search?q=devolução", headers=_headers())
        detail_response = client.get("/api/v1/policies/POL-RETURN-001", headers=_headers())

    assert search_response.status_code == 200
    search_data = search_response.json()
    assert search_data
    assert any(
        "devolução" in f"{policy['title']} {policy['content']}".lower()
        for policy in search_data
    )

    assert detail_response.status_code == 200
    assert detail_response.json() == {
        "id": "POL-RETURN-001",
        "category": "returns",
        "title": "Política de devolução padrão",
        "country": "BR",
        "content": "Produtos podem ser devolvidos em até 30 dias corridos após a entrega, sem custo para o cliente. O item deve estar sem uso, com embalagem original e protocolo de devolução gerado.",
        "effective_from": "2026-01-01",
    }


def test_policy_search_requires_query_and_policy_detail_404s_for_unknown_id() -> None:
    with TestClient(app) as client:
        search_response = client.get("/api/v1/policies/search", headers=_headers())
        detail_response = client.get("/api/v1/policies/POL-UNKNOWN-999", headers=_headers())

    assert search_response.status_code == 422
    assert detail_response.status_code == 404
    assert detail_response.json() == {"detail": "Policy not found"}
