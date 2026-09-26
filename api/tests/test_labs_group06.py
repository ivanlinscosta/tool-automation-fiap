import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


LAB_GROUP = "test-labs-06"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


def _list_po(client: TestClient, group: str = "06", **params: object) -> dict:
    response = client.get(f"{BASE}/{group}/purchase-orders", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def _compose_body(capex: str, supplier_name: str, total: str, items: str = "2 notebooks corporativos") -> str:
    return f"Solicito abertura de compra. CAPEX {capex}. Fornecedor: {supplier_name}. Itens: {items}. Valor total: R$ {total}."


def test_group06_has_at_least_one_thousand_purchase_orders(client: TestClient) -> None:
    assert _list_po(client, limit=1)["meta"]["total"] >= 1000


def test_group06_aliases_unknown_and_wrong_group(client: TestClient) -> None:
    for alias in ("6", "06", "group-6", "group-06"):
        assert _list_po(client, group=alias, limit=1)["meta"]["total"] >= 1000
    assert client.get(f"{BASE}/99/purchase-orders", headers=_headers()).status_code == 404
    wrong = client.get(f"{BASE}/05/purchase-orders", headers=_headers())
    assert wrong.status_code == 404
    assert "does not belong to lab group 06" in wrong.json()["detail"]


def test_group06_filters_sorting_and_missing_entity(client: TestClient) -> None:
    approved = _list_po(client, limit=20, status="APROVADA")
    assert approved["meta"]["total"] > 0
    assert all(item["status"] == "APROVADA" for item in approved["items"])
    ascending = _list_po(client, limit=5, sort="created_at", order="asc")
    descending = _list_po(client, limit=5, sort="created_at", order="desc")
    assert ascending["items"][0]["created_at"] != descending["items"][0]["created_at"]
    invalid = client.get(f"{BASE}/06/purchase-orders", params={"sort": "foo"}, headers=_headers())
    assert invalid.status_code == 400
    missing = client.get(f"{BASE}/06/purchase-orders/PO-999999", headers=_headers())
    assert missing.status_code == 404


def test_group06_email_extract_and_full_approval_workflow(client: TestClient) -> None:
    vendor = client.get(f"{BASE}/06/vendors", params={"ativo": True, "limit": 1}, headers=_headers()).json()["items"][0]
    budget = client.get(f"{BASE}/06/budgets", params={"limit": 1, "sort": "saldo", "order": "desc"}, headers=_headers()).json()["items"][0]
    body = _compose_body(budget["capexNumber"], vendor["nome"], "12.500,00")
    email = client.post(
        f"{BASE}/06/email-requests",
        json={"remetente": "compras@example.com", "assunto": f"Compra {budget['capexNumber']}", "corpo": body},
        headers=_headers(),
    )
    assert email.status_code == 201, email.text
    extracted = client.post(f"{BASE}/06/email-requests/{email.json()['request_id']}/extract", headers=_headers())
    assert extracted.status_code == 200, extracted.text
    request_id = extracted.json()["id"]
    budget_check = client.post(f"{BASE}/06/purchase-requests/{request_id}/check-budget", headers=_headers())
    assert budget_check.status_code == 200
    assert budget_check.json()["approved"] is True
    purchase_order = client.post(f"{BASE}/06/purchase-requests/{request_id}/purchase-order", headers=_headers())
    assert purchase_order.status_code == 201, purchase_order.text
    po_number = purchase_order.json()["purchaseOrderNumber"]
    submit = client.post(f"{BASE}/06/purchase-orders/{po_number}/submit", headers=_headers())
    assert submit.status_code == 200
    stage2_first = client.post(
        f"{BASE}/06/purchase-orders/{po_number}/approve",
        json={"stage": 2, "aprovador": "diretor.financeiro"},
        headers=_headers(),
    )
    assert stage2_first.status_code == 409
    stage1 = client.post(
        f"{BASE}/06/purchase-orders/{po_number}/approve",
        json={"stage": 1, "aprovador": "gerente.compras"},
        headers=_headers(),
    )
    assert stage1.status_code == 200, stage1.text
    duplicate_stage1 = client.post(
        f"{BASE}/06/purchase-orders/{po_number}/approve",
        json={"stage": 1, "aprovador": "gerente.compras"},
        headers=_headers(),
    )
    assert duplicate_stage1.status_code == 409
    stage2 = client.post(
        f"{BASE}/06/purchase-orders/{po_number}/approve",
        json={"stage": 2, "aprovador": "diretor.financeiro"},
        headers=_headers(),
    )
    assert stage2.status_code == 200, stage2.text
    assert stage2.json()["purchase_order"]["status"] == "APROVADA"
    status_response = client.get(f"{BASE}/06/purchase-orders/{po_number}/status", headers=_headers())
    assert status_response.status_code == 200
    assert status_response.json()["fully_approved"] is True


def test_group06_reject_and_budget_conflict_paths(client: TestClient) -> None:
    vendor = client.get(f"{BASE}/06/vendors", params={"ativo": True, "limit": 1}, headers=_headers()).json()["items"][0]
    low_budget = client.get(f"{BASE}/06/budgets", params={"limit": 1, "sort": "saldo", "order": "asc"}, headers=_headers()).json()["items"][0]
    body = _compose_body(low_budget["capexNumber"], vendor["nome"], "999.999,99")
    email = client.post(
        f"{BASE}/06/email-requests",
        json={"remetente": "compras@example.com", "assunto": "Compra critica", "corpo": body},
        headers=_headers(),
    )
    assert email.status_code == 201, email.text
    extracted = client.post(f"{BASE}/06/email-requests/{email.json()['request_id']}/extract", headers=_headers()).json()
    conflict = client.post(f"{BASE}/06/purchase-requests/{extracted['id']}/purchase-order", headers=_headers())
    assert conflict.status_code == 409

    high_budget = client.get(f"{BASE}/06/budgets", params={"limit": 1, "sort": "saldo", "order": "desc"}, headers=_headers()).json()["items"][0]
    body_ok = _compose_body(high_budget["capexNumber"], vendor["nome"], "8.000,00")
    email_ok = client.post(
        f"{BASE}/06/email-requests",
        json={"remetente": "compras@example.com", "assunto": "Compra regular", "corpo": body_ok},
        headers=_headers(),
    ).json()
    req = client.post(f"{BASE}/06/email-requests/{email_ok['request_id']}/extract", headers=_headers()).json()
    po = client.post(f"{BASE}/06/purchase-requests/{req['id']}/purchase-order", headers=_headers()).json()
    client.post(f"{BASE}/06/purchase-orders/{po['purchaseOrderNumber']}/submit", headers=_headers())
    rejected = client.post(
        f"{BASE}/06/purchase-orders/{po['purchaseOrderNumber']}/reject",
        json={"stage": 1, "aprovador": "gerente.compras", "comentario": "Fornecedor fora da politica."},
        headers=_headers(),
    )
    assert rejected.status_code == 200, rejected.text
    again = client.post(
        f"{BASE}/06/purchase-orders/{po['purchaseOrderNumber']}/reject",
        json={"stage": 1, "aprovador": "gerente.compras"},
        headers=_headers(),
    )
    assert again.status_code == 409


def test_group06_rejects_unextractable_email_body(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/06/email-requests",
        json={"remetente": "compras@example.com", "assunto": "Sem dados", "corpo": "Favor verificar isso depois."},
        headers=_headers(),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("validation_error", 422), ("not_found", 404), ("duplicate", 409), ("server_error", 500)],
)
def test_group06_scenarios_read_and_write(client: TestClient, scenario: str, expected: int) -> None:
    read_response = client.get(f"{BASE}/06/purchase-orders", params={"scenario": scenario}, headers=_headers())
    assert read_response.status_code == expected
    po_number = _list_po(client, limit=1)["items"][0]["purchaseOrderNumber"]
    write_response = client.post(
        f"{BASE}/06/purchase-orders/{po_number}/submit",
        params={"scenario": scenario},
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group06_temporal_coherence_referential_integrity_and_determinism(client: TestClient, db_session: Session) -> None:
    from app.labs.registry import purge_group

    emails_total = client.get(f"{BASE}/06/email-requests", params={"limit": 1}, headers=_headers()).json()["meta"]["total"]
    requests_total = client.get(f"{BASE}/06/purchase-requests", params={"limit": 1}, headers=_headers()).json()["meta"]["total"]
    budgets_total = client.get(f"{BASE}/06/budgets", params={"limit": 1}, headers=_headers()).json()["meta"]["total"]
    budgets: set[str] = set()
    for offset in range(0, budgets_total, 200):
        payload = client.get(f"{BASE}/06/budgets", params={"limit": 200, "offset": offset}, headers=_headers()).json()
        budgets.update(item["capexNumber"] for item in payload["items"])
    vendors = {item["supplierId"] for item in client.get(f"{BASE}/06/vendors", params={"limit": 200}, headers=_headers()).json()["items"]}

    requests: list[dict] = []
    for offset in range(0, requests_total, 200):
        requests.extend(client.get(f"{BASE}/06/purchase-requests", params={"limit": 200, "offset": offset}, headers=_headers()).json()["items"])
    purchase_orders: list[dict] = []
    po_total = _list_po(client, limit=1)["meta"]["total"]
    for offset in range(0, po_total, 200):
        purchase_orders.extend(_list_po(client, limit=200, offset=offset)["items"])
    for item in requests:
        assert item["created_at"] <= item["updated_at"]
        assert item["capexNumber"] in budgets
        assert item["supplierId"] in vendors
    for item in purchase_orders:
        assert item["created_at"] <= item["updated_at"]
        assert item["capexNumber"] in budgets
        assert item["supplierId"] in vendors
    assert emails_total >= requests_total >= 1000
    first = _list_po(client, limit=50, sort="purchaseOrderNumber")["items"]
    purge_group(db_session, 6)
    second = _list_po(client, limit=50, sort="purchaseOrderNumber")["items"]
    assert first == second
