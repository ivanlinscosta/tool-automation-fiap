import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings


LAB_GROUP = "test-labs-08"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_requests(client: TestClient, group: str = "08", **params: object) -> dict:
    response = client.get(f"{BASE}/{group}/unlock-requests", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_group08_has_at_least_one_thousand_unlock_requests(client: TestClient) -> None:
    assert _list_requests(client, limit=1)["meta"]["total"] >= 1000


def test_group08_aliases_unknown_and_wrong_group(client: TestClient) -> None:
    for alias in ("8", "08", "group-8", "group-08"):
        assert _list_requests(client, group=alias, limit=1)["meta"]["total"] >= 1000
    assert client.get(f"{BASE}/99/unlock-requests", headers=_headers()).status_code == 404
    wrong = client.get(f"{BASE}/07/unlock-requests", headers=_headers())
    assert wrong.status_code == 404
    assert "does not belong to lab group 08" in wrong.json()["detail"]


def test_group08_filters_sort_and_missing_entity(client: TestClient) -> None:
    suspended = client.get(f"{BASE}/08/contracts", params={"contract_status": "SUSPENSO", "limit": 20}, headers=_headers())
    assert suspended.status_code == 200
    assert all(item["contract_status"] == "SUSPENSO" for item in suspended.json()["items"])
    ascending = _list_requests(client, limit=5, sort="requested_at", order="asc")
    descending = _list_requests(client, limit=5, sort="requested_at", order="desc")
    assert ascending["items"][0]["requested_at"] != descending["items"][0]["requested_at"]
    invalid = client.get(f"{BASE}/08/unlock-requests", params={"sort": "foo"}, headers=_headers())
    assert invalid.status_code == 400
    missing = client.get(f"{BASE}/08/unlock-requests/UR-999999", headers=_headers())
    assert missing.status_code == 404


def test_group08_unlock_workflow_happy_path_and_idempotency(client: TestClient) -> None:
    contract = client.get(
        f"{BASE}/08/contracts",
        params={"contract_status": "ATIVO", "limit": 200},
        headers=_headers(),
    ).json()["items"][0]
    created = client.post(
        f"{BASE}/08/unlock-requests",
        json={"customer_id": contract["customer_id"], "motivo": "Cliente pagara amanha e precisa reativar agora."},
        headers=_headers(),
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["request_id"]
    credit = client.post(f"{BASE}/08/unlock-requests/{request_id}/credit-check", headers=_headers())
    assert credit.status_code == 200, credit.text
    promise = client.post(
        f"{BASE}/08/unlock-requests/{request_id}/promise",
        json={"promessa_pagamento_data": "2026-09-15"},
        headers=_headers(),
    )
    assert promise.status_code == 200, promise.text
    decision = client.post(
        f"{BASE}/08/unlock-requests/{request_id}/decide",
        json={"executed_by": "analista.lab"},
        headers=_headers(),
    )
    assert decision.status_code == 200, decision.text
    second_decision = client.post(f"{BASE}/08/unlock-requests/{request_id}/decide", headers=_headers())
    assert second_decision.status_code == 200
    assert second_decision.json()["decision_id"] == decision.json()["decision_id"]
    provision = client.post(
        f"{BASE}/08/unlock-requests/{request_id}/provision",
        json={"executed_by": "provision.bot"},
        headers=_headers(),
    )
    if decision.json()["decision"] == "LIBERADO":
        assert provision.status_code == 200, provision.text
        assert provision.json()["provisioned"] is True
    else:
        assert provision.status_code == 409


def test_group08_past_promise_and_provision_conflict(client: TestClient) -> None:
    request_id = _list_requests(client, limit=1)["items"][0]["request_id"]
    invalid = client.post(
        f"{BASE}/08/unlock-requests/{request_id}/promise",
        json={"promessa_pagamento_data": "2026-09-10"},
        headers=_headers(),
    )
    assert invalid.status_code == 422


def test_group08_contract_summary_and_ground_truth_privacy(client: TestClient) -> None:
    request_item = _list_requests(client, limit=1)["items"][0]
    assert "decisao_esperada" not in request_item
    instructor = client.get(
        f"{BASE}/08/instructor/unlock-requests/{request_item['request_id']}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert instructor.status_code == 200
    assert "decisao_esperada" in instructor.json()
    summary = client.get(f"{BASE}/08/contracts/{request_item['customer_id']}/summary", headers=_headers())
    assert summary.status_code == 200
    assert "contract" in summary.json()
    stats = client.get(f"{BASE}/08/stats", headers=_headers())
    assert stats.status_code == 200
    assert "requests_by_status" in stats.json()


def test_group08_history_filters_work_through_shared_history_route(client: TestClient) -> None:
    request_id = _list_requests(client, limit=1)["items"][0]["request_id"]
    filtered = client.get(f"{BASE}/08/history", params={"request_id": request_id}, headers=_headers())
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["meta"]["total"] > 0
    assert all(item["request_id"] == request_id for item in filtered.json()["items"])


def test_group08_stats_available_on_own_route_and_shared_route(client: TestClient) -> None:
    own = client.get(f"{BASE}/08/unlock-stats", headers=_headers())
    assert own.status_code == 200, own.text
    body = own.json()
    assert body["requests_by_status"]
    assert body["decisions_by_type"]

    shared = client.get(f"{BASE}/08/stats", headers=_headers())
    assert shared.status_code == 200, shared.text
    assert shared.json() == body

    assert client.get(f"{BASE}/8/unlock-stats", headers=_headers()).status_code == 200
    wrong = client.get(f"{BASE}/07/unlock-stats", headers=_headers())
    assert wrong.status_code == 404
    assert "does not belong to lab group 08" in wrong.json()["detail"]


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("validation_error", 422), ("not_found", 404), ("duplicate", 409), ("server_error", 500)],
)
def test_group08_unlock_stats_scenarios(client: TestClient, scenario: str, expected: int) -> None:
    response = client.get(f"{BASE}/08/unlock-stats", params={"scenario": scenario}, headers=_headers())
    assert response.status_code == expected, (scenario, response.text)


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("validation_error", 422), ("not_found", 404), ("duplicate", 409), ("server_error", 500)],
)
def test_group08_scenarios_read_and_write(client: TestClient, scenario: str, expected: int) -> None:
    read_response = client.get(f"{BASE}/08/unlock-requests", params={"scenario": scenario}, headers=_headers())
    assert read_response.status_code == expected
    request_id = _list_requests(client, limit=1)["items"][0]["request_id"]
    write_response = client.post(
        f"{BASE}/08/unlock-requests/{request_id}/credit-check",
        params={"scenario": scenario},
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group08_temporal_coherence_integrity_and_determinism(client: TestClient, db_session: Session) -> None:
    from app.labs.registry import purge_group

    request_total = _list_requests(client, limit=1)["meta"]["total"]
    requests: list[dict] = []
    for offset in range(0, request_total, 200):
        requests.extend(_list_requests(client, limit=200, offset=offset)["items"])
    contracts_total = client.get(f"{BASE}/08/contracts", params={"limit": 1}, headers=_headers()).json()["meta"]["total"]
    contract_ids: set[str] = set()
    for offset in range(0, contracts_total, 200):
        payload = client.get(f"{BASE}/08/contracts", params={"limit": 200, "offset": offset}, headers=_headers()).json()
        contract_ids.update(item["customer_id"] for item in payload["items"])
    history_total = client.get(f"{BASE}/08/history", params={"limit": 1}, headers=_headers()).json()["meta"]["total"]
    history_items: list[dict] = []
    for offset in range(0, history_total, 200):
        history_items.extend(client.get(f"{BASE}/08/history", params={"limit": 200, "offset": offset}, headers=_headers()).json()["items"])
    for item in requests:
        assert item["customer_id"] in contract_ids
        if item["resolved_at"]:
            assert item["requested_at"] <= item["resolved_at"]
    for item in history_items:
        assert item["customer_id"] in contract_ids
    first = _list_requests(client, limit=50, sort="request_id")["items"]
    purge_group(db_session, 8)
    second = _list_requests(client, limit=50, sort="request_id")["items"]
    assert first == second
