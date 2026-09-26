import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.main import app


LAB_GROUP = "test-labs-01"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _instructor_view(client: TestClient, lead_id: str) -> dict:
    response = client.get(
        f"{BASE}/01/instructor/leads/{lead_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _find_labelled_and_unlabelled(client: TestClient, probes: int = 40) -> tuple[str, str]:
    candidates = [item["lead_id"] for item in _list_leads(client, limit=probes)["items"]]
    labelled: str | None = None
    unlabelled: str | None = None
    for lead_id in candidates:
        view = _instructor_view(client, lead_id)
        if view["categoria_sugerida"] and labelled is None:
            labelled = lead_id
        if not view["categoria_sugerida"] and unlabelled is None:
            unlabelled = lead_id
        if labelled and unlabelled:
            break
    assert labelled is not None, "expected at least one labelled lead"
    assert unlabelled is not None, "expected at least one unlabelled lead"
    return labelled, unlabelled


def _list_leads(client: TestClient, group: str = "01", **params: object) -> dict:
    response = client.get(f"{BASE}/{group}/leads", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_group01_seeds_at_least_one_thousand_leads(client: TestClient) -> None:
    payload = _list_leads(client, limit=1)
    assert payload["meta"]["total"] >= 1000
    assert payload["meta"]["total"] == payload["meta"]["total"]


def test_group01_lazy_seed_happens_once(client: TestClient) -> None:
    first = _list_leads(client, limit=1)
    second = _list_leads(client, limit=1)
    assert first["meta"]["total"] == second["meta"]["total"]


def test_group01_pagination_is_stable_and_non_overlapping(client: TestClient) -> None:
    first = _list_leads(client, limit=10, offset=0, sort="created_at")
    second = _list_leads(client, limit=10, offset=10, sort="created_at")
    assert len(first["items"]) == 10
    assert len(second["items"]) == 10
    first_ids = {item["lead_id"] for item in first["items"]}
    second_ids = {item["lead_id"] for item in second["items"]}
    assert first_ids.isdisjoint(second_ids)
    assert first["meta"]["total_pages"] == -(-first["meta"]["total"] // 10)
    assert first["meta"]["has_more"] is True


def test_group01_offset_beyond_total_returns_empty_page(client: TestClient) -> None:
    payload = _list_leads(client, limit=5, offset=10_000_000)
    assert payload["items"] == []
    assert payload["meta"]["has_more"] is False


@pytest.mark.parametrize("alias", ["1", "01", "group-1", "group-01", "GROUP-01"])
def test_group01_accepts_every_group_alias(client: TestClient, alias: str) -> None:
    assert _list_leads(client, group=alias, limit=1)["meta"]["total"] >= 1000


@pytest.mark.parametrize("bad", ["0", "13", "99", "abc", "group-13", "group-0"])
def test_group01_rejects_unknown_group_alias(client: TestClient, bad: str) -> None:
    response = client.get(f"{BASE}/{bad}/leads", headers=_headers())
    assert response.status_code == 404
    assert "Unknown lab group" in response.json()["detail"]


def test_group01_endpoint_rejects_other_group(client: TestClient) -> None:
    response = client.get(f"{BASE}/02/leads", headers=_headers())
    assert response.status_code == 404
    assert "does not belong to lab group 01" in response.json()["detail"]


def test_group01_filters_by_status_and_origin(client: TestClient) -> None:
    everything = _list_leads(client, limit=1)
    status_filtered = _list_leads(client, limit=50, status="NOVO")
    assert status_filtered["meta"]["total"] < everything["meta"]["total"]
    assert all(item["status"] == "NOVO" for item in status_filtered["items"])

    origin = status_filtered["items"][0]["origem"]
    by_origin = _list_leads(client, limit=50, origem=origin)
    assert all(item["origem"] == origin for item in by_origin["items"])


def test_group01_search_matches_free_text(client: TestClient) -> None:
    payload = _list_leads(client, limit=5, search="orcamento")
    assert payload["meta"]["total"] > 0
    for item in payload["items"]:
        haystack = " ".join(
            str(item.get(field) or "") for field in ("nome", "empresa", "email", "mensagem")
        ).lower()
        assert "orcamento" in haystack


def test_group01_sorting_is_deterministic_and_rejects_unknown_field(client: TestClient) -> None:
    ascending = _list_leads(client, limit=5, sort="created_at", order="asc")
    descending = _list_leads(client, limit=5, sort="created_at", order="desc")
    assert [item["created_at"] for item in ascending["items"]] == sorted(
        item["created_at"] for item in ascending["items"]
    )
    assert ascending["items"][0]["created_at"] != descending["items"][0]["created_at"]

    invalid = client.get(f"{BASE}/01/leads", params={"sort": "campo_inexistente"}, headers=_headers())
    assert invalid.status_code == 400
    assert "Invalid sort field" in invalid.json()["detail"]


def test_group01_contains_duplicate_leads(client: TestClient) -> None:
    everything = _list_leads(client, limit=1)
    total = everything["meta"]["total"]
    seen: dict[str, int] = {}
    offset = 0
    while offset < total:
        for item in _list_leads(client, limit=200, offset=offset)["items"]:
            key = item["duplicate_key"]
            if key:
                seen[key] = seen.get(key, 0) + 1
        offset += 200
    assert any(count > 1 for count in seen.values())


def test_group01_get_lead_by_id(client: TestClient) -> None:
    first = _list_leads(client, limit=1)["items"][0]
    response = client.get(f"{BASE}/01/leads/{first['lead_id']}", headers=_headers())
    assert response.status_code == 200
    assert response.json()["lead_id"] == first["lead_id"]


def test_group01_get_missing_lead_returns_404(client: TestClient) -> None:
    response = client.get(f"{BASE}/01/leads/LEAD-999999", headers=_headers())
    assert response.status_code == 404
    assert response.json()["detail"] == "Lead 'LEAD-999999' not found"


def test_group01_create_lead_starts_as_novo(client: TestClient) -> None:
    payload = {
        "nome": "Helena Braga",
        "empresa": "Estrela Logistica",
        "email": "helena.braga@example.com",
        "telefone": "(11) 98877-1200",
        "origem": "site",
        "segmento": "mid_market",
        "regiao": "Sudeste",
        "produto_interesse": "PROD-01",
        "mensagem": "Precisamos de um orcamento para 40 licencas do Quantum Analytics.",
    }
    response = client.post(f"{BASE}/01/leads", json=payload, headers=_headers())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "NOVO"
    assert body["duplicate_key"] == "helena.braga@example.com"
    assert re.fullmatch(r"LEAD-\d{6}", body["lead_id"])

    stored = client.get(f"{BASE}/01/leads/{body['lead_id']}", headers=_headers()).json()
    assert stored["nome"] == "Helena Braga"
    assert "categoria_sugerida" not in stored


def test_group01_create_duplicate_lead_returns_409(client: TestClient) -> None:
    payload = {"origem": "site", "email": "duplicado@example.com", "mensagem": "Quero um orcamento."}
    assert client.post(f"{BASE}/01/leads", json=payload, headers=_headers()).status_code == 201
    conflict = client.post(f"{BASE}/01/leads", json=payload, headers=_headers())
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Duplicate lead detected"


def test_group01_create_lead_requires_origin(client: TestClient) -> None:
    response = client.post(f"{BASE}/01/leads", json={"nome": "Sem origem"}, headers=_headers())
    assert response.status_code == 422
    assert any(error["loc"] == ["body", "origem"] for error in response.json()["detail"])


def test_group01_check_duplicates_detects_existing_and_missing(client: TestClient) -> None:
    existing = _list_leads(client, limit=200)["items"]
    candidate = next(item for item in existing if item["email"] and "@" in item["email"])

    hit = client.post(
        f"{BASE}/01/leads/check-duplicates",
        json={"origem": "site", "email": candidate["email"], "mensagem": "checagem"},
        headers=_headers(),
    )
    assert hit.status_code == 200
    body = hit.json()
    assert body["is_duplicate"] is True
    assert body["match_reason"] == "email"
    assert body["duplicate_key"] == candidate["email"].strip().lower()
    assert len(body["matches"]) >= 1

    miss = client.post(
        f"{BASE}/01/leads/check-duplicates",
        json={"origem": "site", "email": "ninguem@example.com", "mensagem": "checagem"},
        headers=_headers(),
    )
    assert miss.status_code == 200
    assert miss.json()["is_duplicate"] is False
    assert miss.json()["matches"] == []


def test_group01_check_duplicates_without_contact_info_is_not_duplicate(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/01/leads/check-duplicates",
        json={"origem": "site", "mensagem": "mensagem anonima"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"duplicate_key": "", "is_duplicate": False, "match_reason": "none", "matches": []}


def test_group01_update_status_persists(client: TestClient) -> None:
    lead_id = _list_leads(client, limit=1)["items"][0]["lead_id"]
    response = client.post(
        f"{BASE}/01/leads/{lead_id}/status",
        json={"status": "QUALIFICADO", "qualificado": True},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "QUALIFICADO"
    assert response.json()["qualificado"] == 1

    stored = client.get(f"{BASE}/01/leads/{lead_id}", headers=_headers()).json()
    assert stored["status"] == "QUALIFICADO"


def test_group01_disqualification_requires_motivo(client: TestClient) -> None:
    lead_id = _list_leads(client, limit=1)["items"][0]["lead_id"]
    response = client.post(
        f"{BASE}/01/leads/{lead_id}/status",
        json={"status": "DESQUALIFICADO", "qualificado": False, "motivo_desqualificacao": "Sem orcamento"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["motivo_desqualificacao"] == "Sem orcamento"


def test_group01_assign_known_and_unknown_sales_rep(client: TestClient) -> None:
    lead_id = _list_leads(client, limit=1)["items"][0]["lead_id"]
    ok = client.post(f"{BASE}/01/leads/{lead_id}/assign", json={"responsavel": "SR-02"}, headers=_headers())
    assert ok.status_code == 200
    assert ok.json()["responsavel"] == "SR-02"

    missing = client.post(f"{BASE}/01/leads/{lead_id}/assign", json={"responsavel": "SR-99"}, headers=_headers())
    assert missing.status_code == 404
    assert missing.json()["detail"] == "SalesRep 'SR-99' not found"


def test_group01_sales_reps_expose_arrays(client: TestClient) -> None:
    response = client.get(f"{BASE}/01/sales-reps", params={"limit": 5}, headers=_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total"] >= 10
    for rep in payload["items"]:
        assert isinstance(rep["regioes"], list)
        assert isinstance(rep["segmentos"], list)
        assert isinstance(rep["produtos"], list)


def test_group01_campaigns_and_products_are_listed(client: TestClient) -> None:
    campaigns = client.get(f"{BASE}/01/campaigns", params={"limit": 5}, headers=_headers())
    products = client.get(f"{BASE}/01/products", params={"limit": 5, "segmento": "enterprise"}, headers=_headers())
    assert campaigns.status_code == 200 and campaigns.json()["meta"]["total"] >= 10
    assert products.status_code == 200
    assert all(item["segmento"] == "enterprise" for item in products.json()["items"])


def test_group01_classify_is_instructor_only(client: TestClient) -> None:
    labelled, unlabelled = _find_labelled_and_unlabelled(client)

    anonymous = client.post(f"{BASE}/01/instructor/leads/{labelled}/classify", headers=_headers())
    assert anonymous.status_code == 401
    assert "X-Instructor-Key" in anonymous.json()["detail"]

    wrong_key = client.post(
        f"{BASE}/01/instructor/leads/{labelled}/classify",
        headers=_headers(**{"X-Instructor-Key": "chave-errada"}),
    )
    assert wrong_key.status_code == 401

    ok = client.post(
        f"{BASE}/01/instructor/leads/{labelled}/classify",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert ok.status_code == 200
    assert ok.json()["categoria_sugerida"]

    blocked = client.post(
        f"{BASE}/01/instructor/leads/{unlabelled}/classify",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert blocked.status_code == 422
    assert "ground truth" in blocked.json()["detail"]


def test_group01_instructor_detail_exposes_label(client: TestClient) -> None:
    lead_id, _ = _find_labelled_and_unlabelled(client)
    response = client.get(
        f"{BASE}/01/instructor/leads/{lead_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert response.status_code == 200
    assert response.json()["categoria_sugerida"]


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("validation_error", 422),
        ("not_found", 404),
        ("duplicate", 409),
        ("server_error", 500),
    ],
)
def test_group01_scenarios_on_read(client: TestClient, scenario: str, expected: int) -> None:
    response = client.get(f"{BASE}/01/leads", params={"scenario": scenario}, headers=_headers())
    assert response.status_code == expected
    assert "Simulated" in response.json()["detail"]


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("validation_error", 422),
        ("not_found", 404),
        ("duplicate", 409),
        ("server_error", 500),
    ],
)
def test_group01_scenarios_on_write(client: TestClient, scenario: str, expected: int) -> None:
    lead_id = _list_leads(client, limit=1)["items"][0]["lead_id"]
    response = client.post(
        f"{BASE}/01/leads/{lead_id}/status",
        params={"scenario": scenario},
        json={"status": "CONVERTIDO"},
        headers=_headers(),
    )
    assert response.status_code == expected


def test_group01_timeout_scenario_returns_504(client: TestClient) -> None:
    response = client.get(f"{BASE}/01/leads", params={"scenario": "timeout"}, headers=_headers())
    assert response.status_code == 504
    assert "Simulated timeout" in response.json()["detail"]


def test_group01_unknown_scenario_returns_422(client: TestClient) -> None:
    response = client.get(f"{BASE}/01/leads", params={"scenario": "explodir"}, headers=_headers())
    assert response.status_code == 422
    assert "Unknown scenario" in response.json()["detail"]


def test_group01_success_scenario_is_a_no_op(client: TestClient) -> None:
    payload = _list_leads(client, limit=1, scenario="success")
    assert payload["meta"]["total"] >= 1000


def test_group01_scenario_does_not_mutate_state(client: TestClient) -> None:
    lead_id = _list_leads(client, limit=1)["items"][0]["lead_id"]
    before = client.get(f"{BASE}/01/leads/{lead_id}", headers=_headers()).json()
    client.post(
        f"{BASE}/01/leads/{lead_id}/status",
        params={"scenario": "server_error"},
        json={"status": "DESCARTADO"},
        headers=_headers(),
    )
    after = client.get(f"{BASE}/01/leads/{lead_id}", headers=_headers()).json()
    assert after["status"] == before["status"]


def test_group01_never_leaks_labels_on_list(client: TestClient) -> None:
    payload = _list_leads(client, limit=50)
    allowed = {"lead_id", "nome", "empresa", "email", "telefone", "origem", "segmento", "regiao",
               "produto_interesse", "mensagem", "status", "responsavel", "created_at", "updated_at",
               "ultimo_contato_em", "duplicate_key", "qualificado", "motivo_desqualificacao"}
    for item in payload["items"]:
        assert set(item) <= allowed


def test_group01_never_leaks_labels_on_detail(client: TestClient) -> None:
    lead_id = _list_leads(client, limit=1)["items"][0]["lead_id"]
    body = client.get(f"{BASE}/01/leads/{lead_id}", headers=_headers()).json()
    for leaked in ("categoria_sugerida", "resumo_llm", "confianca_llm"):
        assert leaked not in body


def test_group01_referential_integrity_of_owner(client: TestClient) -> None:
    rep_ids = {item["sales_rep_id"] for item in client.get(f"{BASE}/01/sales-reps", params={"limit": 200}).json()["items"]}
    total = _list_leads(client, limit=1)["meta"]["total"]
    offset = 0
    while offset < total:
        for item in _list_leads(client, limit=200, offset=offset)["items"]:
            assert item["responsavel"] is None or item["responsavel"] in rep_ids
        offset += 200


def test_group01_timestamps_are_coherent(client: TestClient) -> None:
    total = _list_leads(client, limit=1)["meta"]["total"]
    offset = 0
    while offset < total:
        for item in _list_leads(client, limit=200, offset=offset)["items"]:
            assert item["created_at"] <= item["updated_at"]
            if item["ultimo_contato_em"]:
                assert item["created_at"] <= item["ultimo_contato_em"]
        offset += 200


def test_group01_data_is_deterministic_across_reseeds(client: TestClient, db_session: Session) -> None:
    from app.labs.registry import purge_group

    first = _list_leads(client, limit=200)["items"]
    purge_group(db_session, 1)
    second = _list_leads(client, limit=200)["items"]
    assert first == second


def test_group01_instructor_endpoints_disabled_without_configured_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", "")
    response = client.post(
        f"{BASE}/01/instructor/leads/LEAD-000001/classify",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert response.status_code == 403
    assert "LABS_INSTRUCTOR_KEY" in response.json()["detail"]
