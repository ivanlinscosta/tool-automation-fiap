import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.labs.registry import LAB_GROUPS
from app.main import app


INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs"


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _instructor_headers() -> dict[str, str]:
    return {"X-Instructor-Key": INSTRUCTOR_KEY}


def test_labs_meta_describes_platform(client: TestClient) -> None:
    response = client.get(f"{BASE}/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["group_count"] == 12
    assert body["seed"] == 2026
    assert body["reference_date"] == "2026-09-13"
    assert body["min_records_per_group"] == 1000
    assert body["available_groups"] == [f"{i:02d}" for i in range(1, 13)]
    assert set(body["scenarios"]["supported"]) == {
        "success",
        "validation_error",
        "not_found",
        "duplicate",
        "timeout",
        "server_error",
    }
    assert body["conventions"]["pagination"]["envelope"] == ["items", "meta"]


def test_labs_groups_lists_twelve_entries(client: TestClient) -> None:
    response = client.get(f"{BASE}/groups")
    assert response.status_code == 200
    body = response.json()
    assert body["total_groups"] == 12
    assert [group["group_id"] for group in body["groups"]] == [f"{i:02d}" for i in range(1, 13)]
    group_one = body["groups"][0]
    assert group_one["slug"] == "prospeccao-leads"
    assert group_one["seeded"] is False
    assert group_one["total_records"] == 0


def test_labs_groups_reports_seeded_group_without_forcing_seeds(client: TestClient) -> None:
    assert client.get(f"{BASE}/groups/01/leads", params={"limit": 1}).status_code == 200

    body = client.get(f"{BASE}/groups").json()
    group_one = body["groups"][0]
    assert group_one["seeded"] is True
    assert group_one["meets_minimum"] is True
    assert group_one["total_records"] >= 1000


def test_labs_groups_does_not_seed_every_group(client: TestClient) -> None:
    body = client.get(f"{BASE}/groups").json()
    assert [group["seeded"] for group in body["groups"]] == [False] * 12


def test_labs_meta_does_not_seed_groups(client: TestClient) -> None:
    body = client.get(f"{BASE}/meta").json()
    assert body["seeded_groups"] == []
    assert body["available_groups"] == [f"{i:02d}" for i in range(1, 13)]


def test_labs_group_models_exposes_columns(client: TestClient) -> None:
    response = client.get(f"{BASE}/groups/01/models")
    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == "01"
    assert "lab_g01_leads" in body["tables"]
    assert "lead_id" in body["tables"]["lab_g01_leads"]
    assert {"child": "Lead", "field": "responsavel", "parent": "SalesRep.sales_rep_id"} in body["relations"]


def test_labs_group_models_rejects_unknown_group(client: TestClient) -> None:
    assert client.get(f"{BASE}/groups/42/models").status_code == 404


def test_labs_integrity_requires_instructor_key(client: TestClient) -> None:
    assert client.get(f"{BASE}/groups/01/integrity").status_code == 401
    assert client.get(f"{BASE}/groups/01/integrity", headers={"X-Instructor-Key": "errada"}).status_code == 401


def test_labs_integrity_reports_group01_healthy(client: TestClient) -> None:
    response = client.get(f"{BASE}/groups/01/integrity", headers=_instructor_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    assert body["violations"] == []
    assert body["checked_relations"] >= 1


def test_labs_reset_is_idempotent_and_deterministic(client: TestClient) -> None:
    first = client.post(f"{BASE}/reset", json={"groups": [1]}, headers=_instructor_headers())
    assert first.status_code == 200
    assert "01" in first.json()["reset_groups"]

    before = client.get(f"{BASE}/groups/01/leads", params={"limit": 100}).json()["items"]
    client.post(f"{BASE}/reset", json={"groups": [1]}, headers=_instructor_headers())
    after = client.get(f"{BASE}/groups/01/leads", params={"limit": 100}).json()["items"]
    assert before == after


def test_labs_reset_rejects_unknown_group(client: TestClient) -> None:
    response = client.post(f"{BASE}/reset", json={"groups": [99]}, headers=_instructor_headers())
    assert response.status_code == 404
    assert "Unknown lab group" in response.json()["detail"]


def test_labs_reset_all_reports_skipped_groups(client: TestClient) -> None:
    response = client.post(f"{BASE}/reset", json={"groups": None}, headers=_instructor_headers())
    assert response.status_code == 200
    body = response.json()
    assert "01" in body["reset_groups"]
    assert set(body["skipped_groups"]) <= {f"{i:02d}" for i in range(2, 13)}


def test_labs_integrity_disabled_without_configured_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", "")
    response = client.get(f"{BASE}/groups/01/integrity", headers=_instructor_headers())
    assert response.status_code == 403


def test_labs_registry_covers_all_twelve_groups() -> None:
    assert sorted(LAB_GROUPS) == list(range(1, 13))
    for group_id, group in LAB_GROUPS.items():
        assert group.probe in group.models
        assert group.models_module.startswith("app.models.labs.group")
        for child, field, parent in group.relations:
            child_name, _, _ = parent.partition(".")
            assert child in group.models, f"group {group_id}: unknown child {child}"
            assert child_name in group.models, f"group {group_id}: unknown parent {child_name}"
            assert field


def test_startup_seeding_flag_wires_every_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as main_module

    seeded: list[int] = []
    monkeypatch.setattr(main_module.settings, "LABS_SEED_ON_STARTUP", True)
    monkeypatch.setattr(
        "app.labs.registry.ensure_group_seeded",
        lambda _db, group_id: seeded.append(group_id),
    )
    monkeypatch.setattr("app.db.database.SessionLocal", lambda: _NullSession())

    main_module._seed_lab_groups_on_startup()
    assert seeded == list(range(1, 13))


def test_startup_seeding_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main as main_module

    called: list[bool] = []
    monkeypatch.setattr(main_module, "_seed_lab_groups_on_startup", lambda: called.append(True))
    monkeypatch.setattr(main_module.settings, "LABS_SEED_ON_STARTUP", False)

    with TestClient(main_module.app):
        pass
    assert called == []


class _NullSession:
    def __enter__(self) -> "_NullSession":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def rollback(self) -> None:
        return None
