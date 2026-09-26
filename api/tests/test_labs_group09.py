import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.labs.group09_onboarding import (
    AccessMatrix,
    Candidate,
    Equipment,
    Onboarding,
    OnboardingTask,
    SecurityApproval,
)


LAB_GROUP = "test-labs-09"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_candidates(client: TestClient, group: str = "09", **params: object) -> dict:
    response = client.get(
        f"{BASE}/{group}/candidates", params=params, headers=_headers()
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_group09_seeds_at_least_one_thousand_candidates(client: TestClient) -> None:
    assert _list_candidates(client, limit=1)["meta"]["total"] >= 1000


@pytest.mark.parametrize("alias", ["9", "09", "group-9", "group-09", "GROUP-09"])
def test_group09_aliases_work(client: TestClient, alias: str) -> None:
    assert _list_candidates(client, group=alias, limit=1)["meta"]["total"] >= 1000


def test_group09_unknown_and_wrong_group_fail(client: TestClient) -> None:
    unknown = client.get(f"{BASE}/13/candidates", headers=_headers())
    wrong = client.get(f"{BASE}/10/candidates", headers=_headers())
    assert unknown.status_code == 404
    assert wrong.status_code == 404


def test_group09_pagination_filters_sorting_and_invalid_sort(
    client: TestClient,
) -> None:
    first = _list_candidates(client, limit=10, offset=0, sort="id_candidato")
    second = _list_candidates(client, limit=10, offset=10, sort="id_candidato")
    assert {item["id_candidato"] for item in first["items"]}.isdisjoint(
        {item["id_candidato"] for item in second["items"]}
    )
    filtered = _list_candidates(
        client, departamento="Tecnologia", status="APROVADO", limit=50
    )
    assert all(
        item["departamento"] == "Tecnologia" and item["status"] == "APROVADO"
        for item in filtered["items"]
    )
    invalid = client.get(
        f"{BASE}/09/candidates", params={"sort": "nao_existe"}, headers=_headers()
    )
    assert invalid.status_code == 400


def test_group09_student_and_instructor_payloads_are_isolated(
    client: TestClient,
) -> None:
    candidate_id = _list_candidates(client, limit=1)["items"][0]["id_candidato"]
    student = client.get(f"{BASE}/09/candidates/{candidate_id}", headers=_headers())
    instructor = client.get(
        f"{BASE}/09/instructor/candidates/{candidate_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert student.status_code == 200
    assert "decisao_admissao_esperada" not in student.json()
    assert instructor.status_code == 200
    assert instructor.json()["decisao_admissao_esperada"] in {"APROVAR", "REJEITAR"}


def test_group09_create_candidate_equipment_issue_and_admin_access_rules(
    client: TestClient,
) -> None:
    payload = {
        "nome": "Marina Oliveira",
        "email": "marina.g09@example.com",
        "cpf": "123.456.789-09",
        "cargo": "Analista",
        "departamento": "Tecnologia",
        "data_admissao": "2026-09-13",
        "admissao_excecao": True,
        "admissao_motivo": "Cobertura emergencial",
        "decisao_admissao_esperada": "APROVAR",
    }
    created = client.post(f"{BASE}/09/candidates", json=payload, headers=_headers())
    assert created.status_code == 201, created.text
    candidate_id = created.json()["id_candidato"]

    equipment = client.post(
        f"{BASE}/09/candidates/{candidate_id}/equipment",
        json={
            "tipo": "NOTEBOOK",
            "modelo": "QuantumBook Pro 14",
            "serial": "SER-G09-001",
            "solicitacao_motivo": "Admissao",
        },
        headers=_headers(),
    )
    assert equipment.status_code == 201
    blocked_issue = client.post(
        f"{BASE}/09/equipment/{equipment.json()['id']}/issue", headers=_headers()
    )
    assert blocked_issue.status_code == 409

    blocked_admin = client.post(
        f"{BASE}/09/candidates/{candidate_id}/access-matrix",
        json={
            "sistema": "erp-financeiro",
            "perfil": "gestor",
            "nivel_acesso": "ADMIN",
            "aprovado": True,
            "aprovador": "gestor.ti",
        },
        headers=_headers(),
    )
    assert blocked_admin.status_code == 409

    for approval_type in (
        "BACKGROUND_CHECK",
        "RG_CPF",
        "ANTECEDENTES",
        "ACESSO_PRECIFICADO",
    ):
        ok = client.post(
            f"{BASE}/09/candidates/{candidate_id}/security-approvals",
            json={
                "tipo_verificacao": approval_type,
                "status": "APROVADO",
                "verificado_por": "seg.time",
                "parecer": "ok",
            },
            headers=_headers(),
        )
        assert ok.status_code == 200, ok.text

    issued = client.post(
        f"{BASE}/09/equipment/{equipment.json()['id']}/issue", headers=_headers()
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "EMPRESTADO"

    admin = client.post(
        f"{BASE}/09/candidates/{candidate_id}/access-matrix",
        json={
            "sistema": "erp-financeiro",
            "perfil": "gestor",
            "nivel_acesso": "ADMIN",
            "aprovado": True,
            "aprovador": "gestor.ti",
        },
        headers=_headers(),
    )
    assert admin.status_code == 201, admin.text
    assert admin.json()["nivel_acesso"] == "ADMIN"


def test_group09_security_exception_requires_parecer(client: TestClient) -> None:
    candidate_id = _list_candidates(client, limit=1)["items"][0]["id_candidato"]
    response = client.post(
        f"{BASE}/09/candidates/{candidate_id}/security-approvals",
        json={
            "tipo_verificacao": "BACKGROUND_CHECK",
            "status": "EXCEPCAO_APROVADA",
            "verificado_por": "seg.time",
        },
        headers=_headers(),
    )
    assert response.status_code == 422


def test_group09_onboarding_status_and_stats_work(client: TestClient) -> None:
    candidate_id = _list_candidates(client, limit=1)["items"][0]["id_candidato"]
    status_response = client.get(
        f"{BASE}/09/candidates/{candidate_id}/onboarding-status", headers=_headers()
    )
    stats_response = client.get(f"{BASE}/09/onboarding-stats", headers=_headers())
    assert status_response.status_code == 200
    assert stats_response.status_code == 200
    assert stats_response.json()["total_candidates"] >= 1000


def test_group09_temporal_coherence_and_referential_integrity(
    client: TestClient, db_session: Session
) -> None:
    for row in db_session.execute(select(Candidate)).scalars().all():
        assert row.created_at <= row.updated_at
        assert row.updated_at.isoformat() <= "2026-09-13T23:59:59"
        if row.admissao_excecao:
            assert row.admissao_motivo
    candidate_ids = {
        row.id_candidato
        for row in db_session.execute(select(Candidate)).scalars().all()
    }
    for row in db_session.execute(select(Onboarding)).scalars().all():
        assert row.id_candidato in candidate_ids
        assert row.created_at <= row.updated_at
    for row in db_session.execute(select(SecurityApproval)).scalars().all():
        assert row.candidate_id in candidate_ids
        assert row.created_at <= row.updated_at
    for row in db_session.execute(select(Equipment)).scalars().all():
        assert row.candidate_id in candidate_ids
        assert row.created_at <= row.updated_at
    for row in db_session.execute(select(AccessMatrix)).scalars().all():
        assert row.candidate_id in candidate_ids
        assert row.created_at <= row.updated_at
    for row in db_session.execute(select(OnboardingTask)).scalars().all():
        assert row.candidate_id in candidate_ids
        assert row.created_at <= row.updated_at
        if row.concluida_em:
            assert row.created_at <= row.concluida_em
    integrity = client.get(
        "/api/v1/labs/groups/09/integrity",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["healthy"] is True
    assert integrity.json()["violations"] == []


def test_group09_determinism_across_reset(client: TestClient) -> None:
    first = _list_candidates(client, limit=100)["items"]
    reset = client.post(
        "/api/v1/labs/reset",
        json={"groups": [9]},
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert reset.status_code == 200, reset.text
    second = _list_candidates(client, limit=100)["items"]
    assert first == second


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("validation_error", 422),
        ("not_found", 404),
        ("duplicate", 409),
        ("server_error", 500),
    ],
)
def test_group09_scenarios_on_read_and_write(
    client: TestClient, scenario: str, expected: int
) -> None:
    read_response = client.get(
        f"{BASE}/09/candidates", params={"scenario": scenario}, headers=_headers()
    )
    assert read_response.status_code == expected
    candidate_id = _list_candidates(client, limit=1)["items"][0]["id_candidato"]
    write_response = client.post(
        f"{BASE}/09/candidates/{candidate_id}/equipment",
        params={"scenario": scenario},
        json={
            "tipo": "HEADSET",
            "modelo": "QuantumSound",
            "serial": "SER-G09-SCN",
            "solicitacao_motivo": "Teste",
        },
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group09_timeout_and_missing_entity(client: TestClient) -> None:
    timeout = client.get(
        f"{BASE}/09/candidates", params={"scenario": "timeout"}, headers=_headers()
    )
    missing = client.get(f"{BASE}/09/candidates/CAND-999999", headers=_headers())
    assert timeout.status_code == 504
    assert missing.status_code == 404
