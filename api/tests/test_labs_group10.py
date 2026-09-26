from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.labs.generators import LAB_NOW
from app.models.labs.group10_clinic import (
    Appointment,
    PatientMessage,
    Professional,
    Slot,
    Waitlist,
    WorkflowLog,
)


LAB_GROUP = "test-labs-10"
INSTRUCTOR_KEY = "chave-de-instrutor"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", INSTRUCTOR_KEY)


def _list_messages(client: TestClient, group: str = "10", **params: object) -> dict:
    response = client.get(
        f"{BASE}/{group}/patient-messages", params=params, headers=_headers()
    )
    assert response.status_code == 200, response.text
    return response.json()


def _list_appointments(client: TestClient, **params: object) -> dict:
    response = client.get(f"{BASE}/10/appointments", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_group10_seeds_at_least_one_thousand_appointments(client: TestClient) -> None:
    assert _list_appointments(client, limit=1)["meta"]["total"] >= 1000


@pytest.mark.parametrize("alias", ["10", "group-10", "GROUP-10"])
def test_group10_aliases_work(client: TestClient, alias: str) -> None:
    assert _list_messages(client, group=alias, limit=1)["meta"]["total"] >= 1000


def test_group10_student_and_instructor_payloads_are_isolated(
    client: TestClient,
) -> None:
    message_id = _list_messages(client, limit=1)["items"][0]["message_id"]
    student = client.get(f"{BASE}/10/patient-messages/{message_id}", headers=_headers())
    instructor = client.get(
        f"{BASE}/10/instructor/patient-messages/{message_id}",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert student.status_code == 200
    assert "rotulo_confirmacao" not in student.json()
    assert "confianca" not in student.json()
    assert instructor.status_code == 200
    assert instructor.json()["label_intent"]


def test_group10_filters_sorting_history_and_invalid_sort(client: TestClient) -> None:
    filtered = _list_messages(client, intent="CONFIRMAR", human_review=False, limit=20)
    assert all(item["human_review"] is False for item in filtered["items"])
    appointments = _list_appointments(
        client, status="CONFIRMADA", limit=20, sort="appointment_id"
    )
    assert all(item["status"] == "CONFIRMADA" for item in appointments["items"])
    message_id = filtered["items"][0]["message_id"]
    history = client.get(f"{BASE}/10/patient-messages/{message_id}/history", headers=_headers())
    invalid = client.get(
        f"{BASE}/10/patient-messages", params={"sort": "invalido"}, headers=_headers()
    )
    assert history.status_code == 200
    assert history.json()["meta"]["total"] >= 1
    assert invalid.status_code == 400


def test_group10_human_review_gate(client: TestClient, db_session: Session) -> None:
    _list_messages(client, limit=1)
    professional_id = db_session.execute(
        select(Professional.professional_id).limit(1)
    ).scalar_one()
    appointment = Appointment(
        appointment_id="APT-TEST-100",
        patient_id="wa-5511999999100",
        professional_id=professional_id,
        data_hora=LAB_NOW - timedelta(days=1),
        duracao_min=30,
        status="AGENDADA",
        valor=250.0,
        observacoes="teste",
    )
    slot = Slot(
        slot_id="SLT-TEST-100",
        professional_id=professional_id,
        data_hora=LAB_NOW,
        disponivel=True,
        reservado_por=None,
    )
    db_session.add(appointment)
    db_session.add(slot)
    db_session.commit()

    created = client.post(
        f"{BASE}/10/patient-messages",
        json={
            "wa_id": "wa-5511999999100",
            "telefone": "5511999999100",
            "mensagem": "Quero reagendar meu atendimento",
            "appointment_id": "APT-TEST-100",
        },
        headers=_headers(),
    )
    assert created.status_code == 201, created.text
    message_id = created.json()["message_id"]
    classified = client.post(
        f"{BASE}/10/patient-messages/{message_id}/classify",
        json={"intent": "REMARCAR", "confianca": 0.61, "origem": "REGRA"},
        headers=_headers(),
    )
    assert classified.status_code == 200
    blocked = client.post(f"{BASE}/10/patient-messages/{message_id}/apply", headers=_headers())
    assert blocked.status_code == 409

    reviewed = client.post(
        f"{BASE}/10/patient-messages/{message_id}/classify",
        json={
            "intent": "REMARCAR",
            "confianca": 0.61,
            "origem": "HUMANO",
            "reviewed_by": "atendente.1",
        },
        headers=_headers(),
    )
    assert reviewed.status_code == 200
    applied = client.post(f"{BASE}/10/patient-messages/{message_id}/apply", headers=_headers())
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "REMARCADA"


def test_group10_reschedule_conflict_and_waitlist_offer(
    client: TestClient, db_session: Session
) -> None:
    _list_messages(client, limit=1)
    professional_id = db_session.execute(
        select(Professional.professional_id).limit(1)
    ).scalar_one()
    appointment = Appointment(
        appointment_id="APT-TEST-200",
        patient_id="wa-5511999999200",
        professional_id=professional_id,
        data_hora=LAB_NOW - timedelta(days=2),
        duracao_min=30,
        status="AGENDADA",
        valor=190.0,
        observacoes="teste conflito",
    )
    patient = PatientMessage(
        message_id="MSG-TEST-200",
        wa_id="wa-5511999999200",
        telefone="5511999999200",
        mensagem="ola",
        received_at=LAB_NOW - timedelta(days=3),
        rotulo_confirmacao="SAUDACAO",
        confianca=0.8,
        human_review=False,
        appointment_id="APT-TEST-200",
    )
    db_session.add(appointment)
    db_session.add(patient)
    for row in (
        db_session.execute(select(Slot).where(Slot.professional_id == professional_id))
        .scalars()
        .all()
    ):
        row.disponivel = False
    db_session.commit()

    conflict = client.post(
        f"{BASE}/10/appointments/APT-TEST-200/reschedule", headers=_headers()
    )
    assert conflict.status_code == 409

    free_professional = db_session.execute(
        select(Professional)
        .where(
            Professional.especialidade
            == db_session.get(Professional, professional_id).especialidade
        )
        .limit(1)
    ).scalar_one()
    db_session.add(
        Slot(
            slot_id="SLT-TEST-201",
            professional_id=free_professional.professional_id,
            data_hora=LAB_NOW + timedelta(days=2),
            disponivel=True,
            reservado_por=None,
        )
    )
    db_session.commit()

    waitlist = client.post(
        f"{BASE}/10/waitlist",
        json={
            "patient_id": "wa-5511999999200",
            "especialidade": free_professional.especialidade,
            "preferencia_data": (LAB_NOW + timedelta(days=1)).isoformat(),
        },
        headers=_headers(),
    )
    assert waitlist.status_code == 201, waitlist.text
    offered = client.post(
        f"{BASE}/10/waitlist/{waitlist.json()['id']}/offer", headers=_headers()
    )
    assert offered.status_code == 200, offered.text
    assert offered.json()["status"] == "OFERECIDO"


def test_group10_temporal_coherence_and_integrity(
    client: TestClient, db_session: Session
) -> None:
    _list_messages(client, limit=1)
    message_map = {
        row.wa_id: row
        for row in db_session.execute(select(PatientMessage)).scalars().all()
    }
    professional_ids = {
        row.professional_id
        for row in db_session.execute(select(Professional)).scalars().all()
    }
    appointment_ids = {
        row.appointment_id
        for row in db_session.execute(select(Appointment)).scalars().all()
    }
    message_ids = {
        row.message_id
        for row in db_session.execute(select(PatientMessage)).scalars().all()
    }
    for row in db_session.execute(select(Appointment)).scalars().all():
        assert row.patient_id in message_map
        assert row.professional_id in professional_ids
        assert message_map[row.patient_id].received_at <= row.data_hora
    for row in db_session.execute(select(Slot)).scalars().all():
        assert row.professional_id in professional_ids
    for row in db_session.execute(select(Waitlist)).scalars().all():
        assert row.patient_id in message_map
        assert row.created_at <= row.preferencia_data
    for row in db_session.execute(select(WorkflowLog)).scalars().all():
        assert row.appointment_id in appointment_ids
        assert row.message_id is None or row.message_id in message_ids
    integrity = client.get(
        "/api/v1/labs/groups/10/integrity",
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["healthy"] is True


def test_group10_determinism_across_reset(client: TestClient) -> None:
    first = _list_appointments(client, limit=100)["items"]
    reset = client.post(
        "/api/v1/labs/reset",
        json={"groups": [10]},
        headers=_headers(**{"X-Instructor-Key": INSTRUCTOR_KEY}),
    )
    assert reset.status_code == 200, reset.text
    second = _list_appointments(client, limit=100)["items"]
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
def test_group10_scenarios_on_read_and_write(
    client: TestClient, scenario: str, expected: int
) -> None:
    read_response = client.get(
        f"{BASE}/10/patient-messages", params={"scenario": scenario}, headers=_headers()
    )
    assert read_response.status_code == expected
    appointment_id = _list_appointments(client, limit=1)["items"][0]["appointment_id"]
    write_response = client.post(
        f"{BASE}/10/appointments/{appointment_id}/confirm",
        params={"scenario": scenario},
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group10_timeout_and_missing_entities(client: TestClient) -> None:
    timeout = client.get(
        f"{BASE}/10/patient-messages", params={"scenario": "timeout"}, headers=_headers()
    )
    missing_message = client.get(f"{BASE}/10/patient-messages/MSG-999999", headers=_headers())
    missing_appointment = client.get(
        f"{BASE}/10/appointments/APT-999999", headers=_headers()
    )
    assert timeout.status_code == 504
    assert missing_message.status_code == 404
    assert missing_appointment.status_code == 404
