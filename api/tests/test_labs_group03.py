import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.labs.generators import cnpj, group_rng


LAB_GROUP = "test-labs-03"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_opportunities(
    client: TestClient, group: str = "03", **params: object
) -> dict:
    response = client.get(
        f"{BASE}/{group}/opportunities", params=params, headers=_headers()
    )
    assert response.status_code == 200, response.text
    return response.json()


def _list_loads(client: TestClient, **params: object) -> dict:
    response = client.get(f"{BASE}/03/loads", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def _authorized_requesters(client: TestClient, **params: object) -> dict:
    response = client.get(
        f"{BASE}/03/authorized-requesters", params=params, headers=_headers()
    )
    assert response.status_code == 200, response.text
    return response.json()


def _valid_documents() -> tuple[str, str]:
    rng = group_rng(303)
    return cnpj(rng), cnpj(rng)


def _build_load_text(document_a: str, document_b: str) -> str:
    first = (
        f"Estrela Logistica | {document_a} | CRM Enterprise | 145000.0 | "
        "Helena Braga | helena.braga@example.com | proposta"
    )
    second = (
        f"Boreal Energia | {document_b} | Analytics Pro | 92000.0 | Bruno Souza | "
        "bruno.souza@example.com | qualificado"
    )
    return f"{first}\n{second}"


def _build_single_line(document: str) -> str:
    return (
        f"Empresa Teste | {document} | CRM Enterprise | 120000.0 | Ana Silva | "
        "ana.silva@example.com | proposta"
    )


def test_group03_seeds_at_least_one_thousand_opportunities(client: TestClient) -> None:
    payload = _list_opportunities(client, limit=1)
    assert payload["meta"]["total"] >= 1000


def test_group03_pagination_aliases_and_wrong_group(client: TestClient) -> None:
    first = _list_opportunities(client, limit=10, sort="opportunity_id")
    second = _list_opportunities(client, limit=10, offset=10, sort="opportunity_id")
    assert {item["opportunity_id"] for item in first["items"]}.isdisjoint(
        {item["opportunity_id"] for item in second["items"]}
    )

    for alias in ("3", "03", "group-3", "group-03", "GROUP-03"):
        assert (
            _list_opportunities(client, group=alias, limit=1)["meta"]["total"] >= 1000
        )

    wrong = client.get(f"{BASE}/04/opportunities", headers=_headers())
    assert wrong.status_code == 404
    assert "does not belong to lab group 03" in wrong.json()["detail"]


def test_group03_rejects_unknown_group_alias(client: TestClient) -> None:
    response = client.get(f"{BASE}/group-99/opportunities", headers=_headers())
    assert response.status_code == 404
    assert "Unknown lab group" in response.json()["detail"]


def test_group03_filters_search_sort_and_missing_entity(client: TestClient) -> None:
    sample = _list_opportunities(client, limit=20)["items"][0]
    by_stage = _list_opportunities(client, limit=30, stage=sample["stage"])
    assert all(item["stage"] == sample["stage"] for item in by_stage["items"])

    by_load = _list_opportunities(client, limit=30, carga_id=sample["load_id"])
    assert all(item["load_id"] == sample["load_id"] for item in by_load["items"])

    by_product = _list_opportunities(client, limit=30, produto=sample["produto"])
    assert all(item["produto"] == sample["produto"] for item in by_product["items"])

    searched = _list_opportunities(
        client, limit=20, search=sample["empresa"].split()[0].lower()
    )
    assert searched["meta"]["total"] > 0

    ascending = _list_opportunities(client, limit=5, sort="valor", order="asc")
    assert [item["valor"] for item in ascending["items"]] == sorted(
        item["valor"] for item in ascending["items"]
    )
    invalid = client.get(
        f"{BASE}/03/opportunities", params={"sort": "nao_existe"}, headers=_headers()
    )
    assert invalid.status_code == 400

    missing = client.get(f"{BASE}/03/opportunities/OPP-999999", headers=_headers())
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Opportunity 'OPP-999999' not found"


def test_group03_lists_related_entities(client: TestClient) -> None:
    loads = _list_loads(client, limit=5)
    assert loads["meta"]["total"] > 0

    logs = client.get(f"{BASE}/03/load-logs", params={"limit": 5}, headers=_headers())
    contacts = client.get(
        f"{BASE}/03/crm-contacts", params={"limit": 5}, headers=_headers()
    )
    deals = client.get(f"{BASE}/03/crm-deals", params={"limit": 5}, headers=_headers())
    maps = client.get(
        f"{BASE}/03/pipeline-maps", params={"limit": 5}, headers=_headers()
    )
    requesters = client.get(
        f"{BASE}/03/authorized-requesters", params={"limit": 5}, headers=_headers()
    )
    assert (
        logs.status_code
        == contacts.status_code
        == deals.status_code
        == maps.status_code
        == requesters.status_code
        == 200
    )
    assert requesters.json()["meta"]["total"] >= 10


def test_group03_create_load_honours_idempotency_and_creates_crm_sync(
    client: TestClient,
) -> None:
    cnpj_a, cnpj_b = _valid_documents()
    payload = {
        "requester_email": "revops.01@example.com",
        "lista_free_text": _build_load_text(cnpj_a, cnpj_b),
    }
    headers = _headers(**{"Idempotency-Key": "idem-03-a"})
    first = client.post(f"{BASE}/03/loads", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["opportunities_count"] == 2
    assert body["deals_created"] == 2
    assert "payload_hash" not in body

    replay = client.post(f"{BASE}/03/loads", json=payload, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["carga_id"] == body["carga_id"]

    cnpj_c, _ = _valid_documents()
    conflict = client.post(
        f"{BASE}/03/loads",
        json=payload
        | {
            "lista_free_text": payload["lista_free_text"]
            + (
                f"\nNova Empresa | {cnpj_c} | CRM SMB | 30000.0 | Carla Lima | "
                "carla.lima@example.com | novo"
            )
        },
        headers=headers,
    )
    assert conflict.status_code == 409

    sync = client.get(
        f"{BASE}/03/loads/{body['carga_id']}/crm-sync", headers=_headers()
    )
    assert sync.status_code == 200
    assert sync.json()["deals_created"] == 2
    assert all(item["bitrix_id"].startswith("BTRX-") for item in sync.json()["deals"])


def test_group03_unauthorized_requester_creates_rejected_load_log(
    client: TestClient,
) -> None:
    cnpj_a, _ = _valid_documents()
    response = client.post(
        f"{BASE}/03/loads",
        json={
            "requester_email": "intruso@example.com",
            "lista_free_text": _build_single_line(cnpj_a),
        },
        headers=_headers(**{"Idempotency-Key": "idem-03-b"}),
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["message"] == "Requester is not authorized"

    logs = client.get(
        f"{BASE}/03/load-logs",
        params={"carga_id": detail["carga_id"], "level": "ERROR"},
        headers=_headers(),
    )
    assert logs.status_code == 200
    assert logs.json()["meta"]["total"] >= 1


def test_group03_validate_opportunity_persists(client: TestClient) -> None:
    opportunity_id = _list_opportunities(client, limit=1)["items"][0]["opportunity_id"]
    response = client.post(
        f"{BASE}/03/opportunities/{opportunity_id}/validate",
        json={"requested_by": "manual-review"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["opportunity_id"] == opportunity_id


def test_group03_temporal_coherence_and_hidden_fields(client: TestClient) -> None:
    total = _list_opportunities(client, limit=1)["meta"]["total"]
    offset = 0
    while offset < total:
        for item in _list_opportunities(client, limit=200, offset=offset)["items"]:
            assert item["created_at"] <= item["updated_at"]
            assert "payload_hash" not in item
        offset += 200
    for load in _list_loads(client, limit=200)["items"]:
        assert load["created_at"] <= load["updated_at"]
        assert "payload_hash" not in load


def test_group03_integrity_endpoint_reports_healthy(client: TestClient) -> None:
    response = client.get(
        f"{BASE}/03/integrity", headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY})
    )
    assert response.status_code == 200
    assert response.json()["healthy"] is True
    assert response.json()["violations"] == []


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("validation_error", 422),
        ("not_found", 404),
        ("duplicate", 409),
        ("server_error", 500),
    ],
)
def test_group03_scenarios_on_read(
    client: TestClient, scenario: str, expected: int
) -> None:
    response = client.get(
        f"{BASE}/03/opportunities", params={"scenario": scenario}, headers=_headers()
    )
    assert response.status_code == expected


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("validation_error", 422),
        ("not_found", 404),
        ("duplicate", 409),
        ("server_error", 500),
    ],
)
def test_group03_scenarios_on_write(
    client: TestClient, scenario: str, expected: int
) -> None:
    cnpj_a, _ = _valid_documents()
    response = client.post(
        f"{BASE}/03/loads",
        params={"scenario": scenario},
        json={
            "requester_email": "revops.01@example.com",
            "lista_free_text": _build_load_text(cnpj_a, cnpj_a).splitlines()[0],
        },
        headers=_headers(**{"Idempotency-Key": f"scenario-{scenario}"}),
    )
    assert response.status_code == expected


def test_group03_timeout_unknown_and_success_scenarios(client: TestClient) -> None:
    timeout = client.get(
        f"{BASE}/03/opportunities", params={"scenario": "timeout"}, headers=_headers()
    )
    assert timeout.status_code == 504

    unknown = client.get(
        f"{BASE}/03/opportunities", params={"scenario": "explodir"}, headers=_headers()
    )
    assert unknown.status_code == 422

    success = _list_opportunities(client, limit=1, scenario="success")
    assert success["meta"]["total"] >= 1000


def test_group03_scenario_does_not_mutate_state(client: TestClient) -> None:
    cnpj_a, _ = _valid_documents()
    before = _list_loads(client, limit=1)["meta"]["total"]
    client.post(
        f"{BASE}/03/loads",
        params={"scenario": "server_error"},
        json={
            "requester_email": "revops.01@example.com",
            "lista_free_text": _build_single_line(cnpj_a),
        },
        headers=_headers(**{"Idempotency-Key": "scenario-mutate-03"}),
    )
    after = _list_loads(client, limit=1)["meta"]["total"]
    assert after == before


def test_group03_data_is_deterministic_across_reseeds(
    client: TestClient, db_session: Session
) -> None:
    from app.labs.registry import purge_group

    first = _list_opportunities(client, limit=200)["items"]
    purge_group(db_session, 3)
    second = _list_opportunities(client, limit=200)["items"]
    assert first == second
