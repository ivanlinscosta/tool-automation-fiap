import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings


LAB_GROUP = "test-labs-05"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_messages(client: TestClient, group: str = "05", **params: object) -> dict:
    response = client.get(f"{BASE}/{group}/messages", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def _instructor_message(client: TestClient, message_id: str) -> dict:
    response = client.get(
        f"{BASE}/05/instructor/messages/{message_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _all_pages(client: TestClient, path: str, key: str = "items", **params: object) -> list[dict]:
    first = client.get(path, params={**params, "limit": 1}, headers=_headers())
    assert first.status_code == 200, first.text
    total = first.json()["meta"]["total"]
    items: list[dict] = []
    for offset in range(0, total, 200):
        response = client.get(path, params={**params, "limit": 200, "offset": offset}, headers=_headers())
        assert response.status_code == 200, response.text
        items.extend(response.json()[key])
    return items


def test_group05_has_at_least_one_thousand_tickets(client: TestClient) -> None:
    payload = client.get(f"{BASE}/05/tickets", params={"limit": 1}, headers=_headers()).json()
    assert payload["meta"]["total"] >= 1000


def test_group05_pagination_and_aliases_work(client: TestClient) -> None:
    first = _list_messages(client, limit=10, offset=0, sort="created_at")
    second = _list_messages(client, limit=10, offset=10, sort="created_at")
    assert {item["message_id"] for item in first["items"]}.isdisjoint({item["message_id"] for item in second["items"]})
    for alias in ("5", "05", "group-5", "group-05", "GROUP-05"):
        assert _list_messages(client, group=alias, limit=1)["meta"]["total"] >= 1000


def test_group05_rejects_unknown_and_wrong_group(client: TestClient) -> None:
    unknown = client.get(f"{BASE}/99/messages", headers=_headers())
    wrong = client.get(f"{BASE}/06/messages", headers=_headers())
    assert unknown.status_code == 404
    assert wrong.status_code == 404
    assert "does not belong to lab group 05" in wrong.json()["detail"]


def test_group05_filters_search_and_sort(client: TestClient) -> None:
    linked = _list_messages(client, limit=20, com_pedido=True)
    assert linked["meta"]["total"] > 0
    assert all(item["order_id"] for item in linked["items"])
    searched = _list_messages(client, limit=20, search="atras")
    assert searched["meta"]["total"] > 0
    ascending = _list_messages(client, limit=5, sort="created_at", order="asc")
    descending = _list_messages(client, limit=5, sort="created_at", order="desc")
    assert ascending["items"][0]["created_at"] != descending["items"][0]["created_at"]
    invalid = client.get(f"{BASE}/05/messages", params={"sort": "campo_inexistente"}, headers=_headers())
    assert invalid.status_code == 400


def test_group05_search_orders_validates_lookup_inputs(client: TestClient) -> None:
    customer = client.get(f"{BASE}/05/customers", params={"limit": 200}, headers=_headers()).json()["items"]
    with_cpf = next(item for item in customer if item["cpf"])
    ok = client.get(f"{BASE}/05/orders/search", params={"cpf": with_cpf["cpf"]}, headers=_headers())
    assert ok.status_code == 200
    invalid = client.get(f"{BASE}/05/orders/search", params={"cpf": "111.111.111-11"}, headers=_headers())
    assert invalid.status_code == 422
    missing = client.get(f"{BASE}/05/orders/search", params={"telefone": "(99) 99999-9999"}, headers=_headers())
    assert missing.status_code == 404


def test_group05_message_triage_and_response_workflow(client: TestClient) -> None:
    customer = client.get(f"{BASE}/05/customers", params={"limit": 200}, headers=_headers()).json()["items"]
    identified = next(item for item in customer if item["telefone"])
    create = client.post(
        f"{BASE}/05/messages",
        json={"customer_name": identified["nome"], "telefone": identified["telefone"], "texto": "Meu pedido atrasou e preciso de retorno."},
        headers=_headers(),
    )
    assert create.status_code in (200, 201), create.text
    message_id = create.json()["message_id"]
    triage = client.post(
        f"{BASE}/05/messages/{message_id}/triage",
        json={"intencao": "reclamacao_atraso", "telefone": identified["telefone"]},
        headers=_headers(),
    )
    assert triage.status_code == 200, triage.text
    ticket = triage.json()
    assert ticket["resposta_template_id"]
    respond = client.post(
        f"{BASE}/05/tickets/{ticket['ticket_id']}/respond",
        json={"template_id": ticket["resposta_template_id"], "resposta_manual": "Transportadora acionada."},
        headers=_headers(),
    )
    assert respond.status_code == 200, respond.text
    assert respond.json()["status"] == "RESPONDIDO"
    again = client.post(
        f"{BASE}/05/tickets/{ticket['ticket_id']}/respond",
        json={"template_id": ticket["resposta_template_id"]},
        headers=_headers(),
    )
    assert again.status_code == 200
    different = client.post(
        f"{BASE}/05/tickets/{ticket['ticket_id']}/respond",
        json={"template_id": "TPL-0001" if ticket["resposta_template_id"] != "TPL-0001" else "TPL-0002"},
        headers=_headers(),
    )
    assert different.status_code == 409


def test_group05_missing_entities_and_ground_truth_protection(client: TestClient) -> None:
    missing_ticket = client.get(f"{BASE}/05/tickets/TCK-PV-999999", headers=_headers())
    assert missing_ticket.status_code == 404
    message = _list_messages(client, limit=1)["items"][0]
    assert "intencao" not in message
    instructor_view = _instructor_message(client, message["message_id"])
    assert instructor_view["intencao"]


def test_group05_stats_and_instructor_auth(client: TestClient) -> None:
    stats = client.get(f"{BASE}/05/stats", headers=_headers())
    assert stats.status_code == 200
    body = stats.json()
    assert body["messages_by_intencao"]
    blocked = client.get(f"{BASE}/05/instructor/messages/MSG-PV-000001", headers=_headers())
    assert blocked.status_code == 401


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("validation_error", 422), ("not_found", 404), ("duplicate", 409), ("server_error", 500)],
)
def test_group05_scenarios_on_read_and_write(client: TestClient, scenario: str, expected: int) -> None:
    read_response = client.get(f"{BASE}/05/messages", params={"scenario": scenario}, headers=_headers())
    assert read_response.status_code == expected
    message_id = _list_messages(client, limit=1)["items"][0]["message_id"]
    write_response = client.post(
        f"{BASE}/05/messages/{message_id}/triage",
        params={"scenario": scenario},
        json={"intencao": "rastreio_pedido"},
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group05_timeout_and_unknown_scenario(client: TestClient) -> None:
    timeout = client.get(f"{BASE}/05/messages", params={"scenario": "timeout"}, headers=_headers())
    unknown = client.get(f"{BASE}/05/messages", params={"scenario": "explode"}, headers=_headers())
    assert timeout.status_code == 504
    assert unknown.status_code == 422


def test_group05_temporal_coherence_and_referential_integrity(client: TestClient) -> None:
    customers = {item["customer_id"] for item in _all_pages(client, f"{BASE}/05/customers")}
    orders = {item["order_id"]: item for item in _all_pages(client, f"{BASE}/05/orders")}
    messages = _all_pages(client, f"{BASE}/05/messages")
    tickets = _all_pages(client, f"{BASE}/05/tickets")
    shipments = _all_pages(client, f"{BASE}/05/shipments")
    for item in messages:
        assert item["created_at"] <= item["updated_at"]
        assert item["customer_id"] is None or item["customer_id"] in customers
        assert item["order_id"] is None or item["order_id"] in orders
    for item in tickets:
        assert item["created_at"] <= item["updated_at"]
        assert item["customer_id"] is None or item["customer_id"] in customers
        assert item["order_id"] is None or item["order_id"] in orders
    for item in shipments:
        assert item["created_at"] <= item["updated_at"]
        assert item["order_id"] in orders
        if item["data_envio"] and item["data_entrega_real"]:
            assert item["data_envio"] <= item["data_entrega_real"]


def test_group05_data_is_deterministic_across_reseeds(client: TestClient, db_session: Session) -> None:
    from app.labs.registry import purge_group

    first = _list_messages(client, limit=100, sort="message_id")["items"]
    purge_group(db_session, 5)
    second = _list_messages(client, limit=100, sort="message_id")["items"]
    assert first == second
