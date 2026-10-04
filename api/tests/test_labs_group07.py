import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings


LAB_GROUP = "test-labs-07"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_receivables(client: TestClient, group: str = "07", **params: object) -> dict:
    response = client.get(f"{BASE}/{group}/receivables", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_group07_has_at_least_one_thousand_receivables(client: TestClient) -> None:
    assert _list_receivables(client, limit=1)["meta"]["total"] >= 1000


def test_group07_aliases_wrong_group_and_unknown_group(client: TestClient) -> None:
    for alias in ("7", "07", "group-7", "group-07"):
        assert _list_receivables(client, group=alias, limit=1)["meta"]["total"] >= 1000
    assert client.get(f"{BASE}/99/receivables", headers=_headers()).status_code == 404
    wrong = client.get(f"{BASE}/08/receivables", headers=_headers())
    assert wrong.status_code == 404
    assert "does not belong to lab group 07" in wrong.json()["detail"]


def test_group07_filters_search_and_sort(client: TestClient) -> None:
    overdue = _list_receivables(client, overdue_only=True, limit=20)
    assert overdue["meta"]["total"] > 0
    assert all(item["dias_atraso"] > 0 for item in overdue["items"])
    faixa = _list_receivables(client, faixa="16-30", limit=20)
    assert all(16 <= item["dias_atraso"] <= 30 for item in faixa["items"])
    lowest = _list_receivables(client, sort="dias_atraso", order="asc", limit=1)["items"][0]["dias_atraso"]
    highest = _list_receivables(client, sort="dias_atraso", order="desc", limit=1)["items"][0]["dias_atraso"]
    assert 1 <= lowest <= highest <= 200
    searched = _list_receivables(client, search="TIT-", limit=5)
    assert searched["meta"]["total"] > 0
    invalid = client.get(f"{BASE}/07/receivables", params={"sort": "foo"}, headers=_headers())
    assert invalid.status_code == 400


def test_group07_collection_decision_send_and_idempotency(client: TestClient) -> None:
    candidate = _list_receivables(client, status="VENCIDO", limit=50)["items"][0]
    decision = client.get(f"{BASE}/07/receivables/{candidate['id_titulo']}/collection-decision", headers=_headers())
    assert decision.status_code == 200
    first = client.post(f"{BASE}/07/receivables/{candidate['id_titulo']}/send-collection", headers=_headers())
    assert first.status_code == 200, first.text
    second = client.post(f"{BASE}/07/receivables/{candidate['id_titulo']}/send-collection", headers=_headers())
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_group07_bulk_send_write_off_and_retry(client: TestClient) -> None:
    batch = client.post(f"{BASE}/07/receivables/bulk-send", json={"faixa": "31-60", "limit": 20}, headers=_headers())
    assert batch.status_code == 200, batch.text
    assert batch.json()["processed"] <= 20
    failed_rows = client.get(f"{BASE}/07/history", params={"resultado": "FALHA", "limit": 20}, headers=_headers())
    assert failed_rows.status_code == 200
    retry = client.post(f"{BASE}/07/process-retry", headers=_headers())
    assert retry.status_code == 200, retry.text

    receivable = _list_receivables(client, limit=1)["items"][0]
    write_off = client.post(
        f"{BASE}/07/receivables/{receivable['id_titulo']}/write-off",
        json={"motivo": "Acordo fechado"},
        headers=_headers(),
    )
    assert write_off.status_code == 200, write_off.text
    assert write_off.json()["status"] == "CANCELADO"


def test_group07_aging_missing_entity_and_ground_truth_privacy(client: TestClient) -> None:
    aging = client.get(f"{BASE}/07/receivables/aging", headers=_headers())
    assert aging.status_code == 200
    missing = client.get(f"{BASE}/07/receivables/TIT-999999", headers=_headers())
    assert missing.status_code == 404
    item = _list_receivables(client, limit=1)["items"][0]
    assert "deve_enviar" not in item
    instructor = client.get(
        f"{BASE}/07/instructor/receivables/{item['id_titulo']}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert instructor.status_code == 200
    assert "deve_enviar" in instructor.json()


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("validation_error", 422), ("not_found", 404), ("duplicate", 409), ("server_error", 500)],
)
def test_group07_scenarios_read_and_write(client: TestClient, scenario: str, expected: int) -> None:
    read_response = client.get(f"{BASE}/07/receivables", params={"scenario": scenario}, headers=_headers())
    assert read_response.status_code == expected
    receivable_id = _list_receivables(client, limit=1)["items"][0]["id_titulo"]
    write_response = client.post(
        f"{BASE}/07/receivables/{receivable_id}/send-collection",
        params={"scenario": scenario},
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group07_temporal_coherence_integrity_and_determinism(client: TestClient, db_session: Session) -> None:
    from app.labs.registry import purge_group

    total = _list_receivables(client, limit=1)["meta"]["total"]
    receivables: list[dict] = []
    for offset in range(0, total, 200):
        receivables.extend(_list_receivables(client, limit=200, offset=offset)["items"])
    history_total = client.get(f"{BASE}/07/history", params={"limit": 1}, headers=_headers()).json()["meta"]["total"]
    history_items: list[dict] = []
    for offset in range(0, history_total, 200):
        history_items.extend(client.get(f"{BASE}/07/history", params={"limit": 200, "offset": offset}, headers=_headers()).json()["items"])
    ids = {item["id_titulo"] for item in receivables}
    for item in receivables:
        assert item["data_emissao"] <= item["updated_at"]
        if item["paid_at"]:
            assert item["data_vencimento"] <= item["paid_at"]
    for item in history_items:
        assert item["id_titulo"] in ids
    first = _list_receivables(client, limit=50, sort="id_titulo")["items"]
    purge_group(db_session, 7)
    second = _list_receivables(client, limit=50, sort="id_titulo")["items"]
    assert first == second
