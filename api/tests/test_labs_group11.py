import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.labs.group11_evidences import (
    ActionPlan,
    EvidenceRegistry,
    IncomingEmail,
    RestoreEvidence,
)


LAB_GROUP = "test-labs-11"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_evidence(client: TestClient, **params: object) -> dict:
    response = client.get(f"{BASE}/11/evidence", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_group11_seeds_at_least_one_thousand_evidence_rows(client: TestClient) -> None:
    assert _list_evidence(client, limit=1)["meta"]["total"] >= 1000


def test_group11_filters_hidden_decision_sort_and_invalid_sort(
    client: TestClient,
) -> None:
    filtered = _list_evidence(client, sistema="erp", limit=20, sort="evidence_id")
    assert all(item["sistema"] == "erp" for item in filtered["items"])
    evidence_id = filtered["items"][0]["evidence_id"]
    student = client.get(f"{BASE}/11/evidence/{evidence_id}", headers=_headers())
    instructor = client.get(
        f"{BASE}/11/instructor/evidence/{evidence_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    invalid = client.get(
        f"{BASE}/11/evidence", params={"sort": "campo_invalido"}, headers=_headers()
    )
    assert "decisao" not in student.json()
    assert instructor.json()["decisao"] in {"APROVADO", "REPROVADO"}
    assert invalid.status_code == 400


def test_group11_pdf_determinism_and_analysis(client: TestClient) -> None:
    evidence_id = _list_evidence(client, limit=1)["items"][0]["evidence_id"]
    first = client.get(f"{BASE}/11/evidence/{evidence_id}/pdf", headers=_headers())
    second = client.get(f"{BASE}/11/evidence/{evidence_id}/pdf", headers=_headers())
    analysis = client.get(
        f"{BASE}/11/evidence/{evidence_id}/analysis", headers=_headers()
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.content == second.content
    assert first.headers["content-type"].startswith("application/pdf")
    assert int(first.headers["content-length"]) > 0
    assert analysis.status_code == 200
    assert "divergent_fields" in analysis.json()


def test_group11_create_review_idempotent_and_complete_action_plan(
    client: TestClient,
) -> None:
    email = client.post(
        f"{BASE}/11/emails",
        json={
            "remetente": "ops@example.com",
            "assunto": "Restore CHG-9001",
            "corpo": "Enviar evidencia",
            "ticket_mudanca": "CHG-9001",
            "severidade": "ALTA",
        },
        headers=_headers(),
    )
    assert email.status_code == 201, email.text
    evidence = client.post(
        f"{BASE}/11/emails/{email.json()['email_id']}/evidence",
        json={
            "IC": "IC-NEW-9001",
            "data_hora_teste": "2026-09-13T09:00:00",
            "resultado": "SUCESSO",
            "sistema": "crm",
            "versao_antes": "5.8.0",
            "versao_depois": "5.9.0",
            "duracao_seg": 500,
            "responsavel": "analista",
            "observacoes": "ok",
            "has_prints": True,
        },
        headers=_headers(),
    )
    assert evidence.status_code == 201, evidence.text
    reviewed = client.post(
        f"{BASE}/11/evidence/{evidence.json()['evidence_id']}/review",
        json={"status": "APROVADO", "analisado_por": "gestor", "parecer": "ok"},
        headers=_headers(),
    )
    replay = client.post(
        f"{BASE}/11/evidence/{evidence.json()['evidence_id']}/review",
        json={
            "status": "REPROVADO",
            "analisado_por": "outro",
            "parecer": "nao importa",
        },
        headers=_headers(),
    )
    assert reviewed.status_code == 200 and replay.status_code == 200
    assert reviewed.json()["id"] == replay.json()["id"]
    plan = client.post(
        f"{BASE}/11/evidence/{evidence.json()['evidence_id']}/action-plans",
        json={
            "acao": "Atualizar runbook",
            "prazo": "2026-09-20",
            "responsavel": "owner",
        },
        headers=_headers(),
    )
    assert plan.status_code == 201, plan.text
    completed = client.post(
        f"{BASE}/11/action-plans/{plan.json()['id']}/complete",
        json={"conclusao": "Concluido"},
        headers=_headers(),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "CONCLUIDA"


def test_group11_temporal_coherence_and_integrity(
    client: TestClient, db_session: Session
) -> None:
    emails = {
        row.email_id: row
        for row in db_session.execute(select(IncomingEmail)).scalars().all()
    }
    evidences = {
        row.evidence_id: row
        for row in db_session.execute(select(RestoreEvidence)).scalars().all()
    }
    ic_values = {row.IC for row in evidences.values()}
    for row in evidences.values():
        assert row.email_id in emails
        assert emails[row.email_id].recebido_em <= row.data_hora_teste
    for row in db_session.execute(select(EvidenceRegistry)).scalars().all():
        assert row.IC in ic_values
    for row in db_session.execute(select(ActionPlan)).scalars().all():
        assert row.evidence_id in evidences
        if row.concluded_at:
            assert row.created_at <= row.concluded_at
    integrity = client.get(
        "/api/v1/labs/groups/11/integrity",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["healthy"] is True


def test_group11_determinism_across_reset(client: TestClient) -> None:
    first = _list_evidence(client, limit=100)["items"]
    reset = client.post(
        "/api/v1/labs/reset",
        json={"groups": [11]},
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert reset.status_code == 200, reset.text
    second = _list_evidence(client, limit=100)["items"]
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
def test_group11_scenarios_on_read_and_write(
    client: TestClient, scenario: str, expected: int
) -> None:
    read_response = client.get(
        f"{BASE}/11/evidence", params={"scenario": scenario}, headers=_headers()
    )
    assert read_response.status_code == expected
    email_id = client.get(
        f"{BASE}/11/emails", params={"limit": 1}, headers=_headers()
    ).json()["items"][0]["email_id"]
    write_response = client.post(
        f"{BASE}/11/emails/{email_id}/evidence",
        params={"scenario": scenario},
        json={
            "IC": "IC-SCN-11",
            "data_hora_teste": "2026-09-13T09:00:00",
            "resultado": "SUCESSO",
            "sistema": "crm",
            "versao_antes": "5.8.0",
            "versao_depois": "5.9.0",
            "duracao_seg": 500,
            "responsavel": "analista",
            "observacoes": "ok",
            "has_prints": True,
        },
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group11_timeout_and_missing_entity(client: TestClient) -> None:
    timeout = client.get(
        f"{BASE}/11/evidence", params={"scenario": "timeout"}, headers=_headers()
    )
    missing = client.get(f"{BASE}/11/evidence/EVD-999999", headers=_headers())
    assert timeout.status_code == 504
    assert missing.status_code == 404
