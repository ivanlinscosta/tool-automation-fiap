import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings


LAB_GROUP = "test-labs-04"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_events(client: TestClient, group: str = "04", **params: object) -> dict:
    response = client.get(
        f"{BASE}/{group}/customer-events", params=params, headers=_headers()
    )
    assert response.status_code == 200, response.text
    return response.json()


def _instructor_view(client: TestClient, event_id: str) -> dict:
    response = client.get(
        f"{BASE}/04/instructor/customer-events/{event_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_group04_seeds_at_least_one_thousand_customer_events(
    client: TestClient,
) -> None:
    payload = _list_events(client, limit=1)
    assert payload["meta"]["total"] >= 1000


def test_group04_pagination_aliases_and_wrong_group(client: TestClient) -> None:
    first = _list_events(client, limit=10, sort="event_id")
    second = _list_events(client, limit=10, offset=10, sort="event_id")
    assert {item["event_id"] for item in first["items"]}.isdisjoint(
        {item["event_id"] for item in second["items"]}
    )

    for alias in ("4", "04", "group-4", "group-04", "GROUP-04"):
        assert _list_events(client, group=alias, limit=1)["meta"]["total"] >= 1000

    wrong = client.get(f"{BASE}/03/customer-events", headers=_headers())
    assert wrong.status_code == 404
    assert "does not belong to lab group 04" in wrong.json()["detail"]


def test_group04_rejects_unknown_group_alias(client: TestClient) -> None:
    response = client.get(f"{BASE}/group-99/customer-events", headers=_headers())
    assert response.status_code == 404
    assert "Unknown lab group" in response.json()["detail"]


def test_group04_filters_sort_and_search(client: TestClient) -> None:
    sample = _list_events(client, limit=50)["items"][0]
    by_channel = _list_events(client, limit=30, canal=sample["canal"])
    assert all(item["canal"] == sample["canal"] for item in by_channel["items"])

    label = _instructor_view(client, sample["event_id"])["intencao"]
    by_intent = _list_events(client, limit=30, intencao=label)
    assert by_intent["meta"]["total"] > 0

    by_priority = _list_events(client, limit=30, prioridade=sample["prioridade"])
    assert all(
        item["prioridade"] == sample["prioridade"] for item in by_priority["items"]
    )

    unrouted = _list_events(client, limit=30, has_department=False)
    assert unrouted["meta"]["total"] > 0
    assert all(item["departamento"] is None for item in unrouted["items"])

    searched = _list_events(client, limit=20, search=sample["customer_id"].lower())
    assert searched["meta"]["total"] > 0

    ascending = _list_events(client, limit=5, sort="sla_horas", order="asc")
    assert [item["sla_horas"] for item in ascending["items"]] == sorted(
        item["sla_horas"] for item in ascending["items"]
    )

    invalid = client.get(
        f"{BASE}/04/customer-events", params={"sort": "nao_existe"}, headers=_headers()
    )
    assert invalid.status_code == 400


def test_group04_student_payload_never_leaks_ground_truth(client: TestClient) -> None:
    payload = _list_events(client, limit=20)
    for item in payload["items"]:
        assert "intencao" not in item
        assert "confianca" not in item
        assert "impacto" not in item
        assert "urgencia" not in item

    event_id = payload["items"][0]["event_id"]
    detail = client.get(f"{BASE}/04/customer-events/{event_id}", headers=_headers())
    assert detail.status_code == 200
    for leaked in ("intencao", "confianca", "impacto", "urgencia"):
        assert leaked not in detail.json()


def test_group04_instructor_detail_requires_key_and_exposes_label(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_id = _list_events(client, limit=1)["items"][0]["event_id"]
    anonymous = client.get(
        f"{BASE}/04/instructor/customer-events/{event_id}", headers=_headers()
    )
    assert anonymous.status_code == 401

    ok = _instructor_view(client, event_id)
    assert ok["intencao"]
    assert ok["confianca"] >= 0.6

    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", "")
    disabled = client.get(
        f"{BASE}/04/instructor/customer-events/{event_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert disabled.status_code == 403


def test_group04_create_route_resolve_and_departments(client: TestClient) -> None:
    created = client.post(
        f"{BASE}/04/customer-events",
        json={
            "customer_id": "CUS-LAB-NEW-1",
            "canal": "whatsapp",
            "mensagem": "Quero cancelar minha assinatura antes da renovacao.",
            "impacto": "alto",
            "urgencia": "alto",
        },
        headers=_headers(),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["prioridade"] == "P1"
    assert body["departamento"] is None

    departments = client.get(
        f"{BASE}/04/departments",
        params={"active_only": True, "limit": 20},
        headers=_headers(),
    )
    assert departments.status_code == 200
    assert all(item["ativo"] is True for item in departments.json()["items"])

    routed = client.post(
        f"{BASE}/04/customer-events/{body['event_id']}/route",
        json={"departamento": "DEP-01"},
        headers=_headers(),
    )
    assert routed.status_code == 200
    assert routed.json()["departamento"] == "DEP-01"

    resolved = client.post(
        f"{BASE}/04/customer-events/{body['event_id']}/resolve",
        json={"status": "resolvido"},
        headers=_headers(),
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolvido"
    assert resolved.json()["resolved_at"] is not None


def test_group04_stats_and_missing_event(client: TestClient) -> None:
    stats = client.get(f"{BASE}/04/customer-events/stats", headers=_headers())
    assert stats.status_code == 200
    assert stats.json()["meta"]["total"] > 0

    missing = client.get(f"{BASE}/04/customer-events/EVT-999999", headers=_headers())
    assert missing.status_code == 404
    assert missing.json()["detail"] == "CustomerEvent 'EVT-999999' not found"


def test_group04_temporal_coherence_and_integrity(client: TestClient) -> None:
    total = _list_events(client, limit=1)["meta"]["total"]
    offset = 0
    while offset < total:
        for item in _list_events(client, limit=200, offset=offset)["items"]:
            if item["resolved_at"]:
                assert item["created_at"] <= item["resolved_at"]
        offset += 200

    integrity = client.get(
        f"{BASE}/04/integrity", headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY})
    )
    assert integrity.status_code == 200
    assert integrity.json()["healthy"] is True
    assert integrity.json()["violations"] == []


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("validation_error", 422),
        ("not_found", 404),
        ("duplicate", 409),
        ("server_error", 500),
    ],
)
def test_group04_scenarios_on_read(
    client: TestClient, scenario: str, expected: int
) -> None:
    response = client.get(
        f"{BASE}/04/customer-events", params={"scenario": scenario}, headers=_headers()
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
def test_group04_scenarios_on_write(
    client: TestClient, scenario: str, expected: int
) -> None:
    response = client.post(
        f"{BASE}/04/customer-events",
        params={"scenario": scenario},
        json={
            "customer_id": "CUS-LAB-SCENARIO",
            "canal": "chat",
            "mensagem": "Tenho duvida sobre a integracao do produto.",
            "impacto": "medio",
            "urgencia": "medio",
        },
        headers=_headers(),
    )
    assert response.status_code == expected


def test_group04_timeout_unknown_and_success_scenarios(client: TestClient) -> None:
    timeout = client.get(
        f"{BASE}/04/customer-events", params={"scenario": "timeout"}, headers=_headers()
    )
    assert timeout.status_code == 504

    unknown = client.get(
        f"{BASE}/04/customer-events",
        params={"scenario": "explodir"},
        headers=_headers(),
    )
    assert unknown.status_code == 422

    success = _list_events(client, limit=1, scenario="success")
    assert success["meta"]["total"] >= 1000


def test_group04_scenario_does_not_mutate_state(client: TestClient) -> None:
    before = _list_events(client, limit=1)["meta"]["total"]
    client.post(
        f"{BASE}/04/customer-events",
        params={"scenario": "server_error"},
        json={
            "customer_id": "CUS-LAB-MUTATE",
            "canal": "email",
            "mensagem": "Quero fazer upgrade do plano.",
            "impacto": "medio",
            "urgencia": "alto",
        },
        headers=_headers(),
    )
    after = _list_events(client, limit=1)["meta"]["total"]
    assert after == before


def test_group04_data_is_deterministic_across_reseeds(
    client: TestClient, db_session: Session
) -> None:
    from app.labs.registry import purge_group

    first = _list_events(client, limit=200)["items"]
    purge_group(db_session, 4)
    second = _list_events(client, limit=200)["items"]
    assert first == second
