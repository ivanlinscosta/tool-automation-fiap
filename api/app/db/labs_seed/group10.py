import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group10 import INTENT_MESSAGES
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    brazilian_phone,
    group_rng,
    money,
    next_moment,
    percentage,
    person_name,
    previous_moment,
)


logger = logging.getLogger(__name__)

ESPECIALIDADES = ("Cardiologia", "Dermatologia", "Neurologia", "Ortopedia", "Pediatria")


def _already_seeded(db: Session, model) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def seed_group(db: Session) -> None:
    from ...models.labs.group10_clinic import (
        Appointment,
        PatientMessage,
        PatientMessageLabel,
        Professional,
        Slot,
        Waitlist,
        WorkflowLog,
    )

    if _already_seeded(db, Appointment):
        logger.info("Group 10 already seeded")
        return

    rng = group_rng(10)
    total = LAB_MIN_RECORDS + 48
    professionals: list[Professional] = []
    messages: list[PatientMessage] = []
    labels: list[PatientMessageLabel] = []
    appointments: list[Appointment] = []
    slots: list[Slot] = []
    waitlist_rows: list[Waitlist] = []
    logs: list[WorkflowLog] = []

    for index in range(16):
        professionals.append(
            Professional(
                professional_id=f"PRO-{index + 1:03d}",
                nome=person_name(rng),
                especialidade=ESPECIALIDADES[index % len(ESPECIALIDADES)],
                registro=f"CRM/{['SP', 'RJ', 'MG', 'PR'][index % 4]} {10000 + index}",
                ativo=index % 7 != 0,
            )
        )

    for index in range(240):
        professional = professionals[index % len(professionals)]
        slot_time = previous_moment(
            rng, LAB_NOW + timedelta(days=25), min_minutes=60, max_days=0
        )
        slots.append(
            Slot(
                slot_id=f"SLT-{index + 1:05d}",
                professional_id=professional.professional_id,
                data_hora=slot_time,
                disponivel=index % 4 != 0,
                reservado_por=None,
            )
        )

    intent_cycle = (
        "CONFIRMAR",
        "CANCELAR",
        "REMARCAR",
        "DUVIDA",
        "RECUSA",
        "SAUDACAO",
        "RUIDO",
    )
    for index in range(total):
        number = index + 1
        received_at = previous_moment(rng, LAB_NOW, min_minutes=120, max_days=90)
        appointment_time = next_moment(rng, received_at, min_minutes=180, max_days=20)
        professional = professionals[index % len(professionals)]
        wa_id = f"wa-55{11000000000 + number}"
        intent = intent_cycle[index % len(intent_cycle)]
        confianca = 0.62 if number % 11 == 0 else percentage(rng, 0.78, 0.99)
        human_review = confianca < 0.75
        if intent == "CONFIRMAR":
            status = "CONFIRMADA"
        elif intent in {"CANCELAR", "RECUSA"}:
            status = "CANCELADA_POR_PACIENTE"
        elif intent == "REMARCAR":
            status = "REMARCADA"
        else:
            status = "AGENDADA"

        appointments.append(
            Appointment(
                appointment_id=f"APT-{number:06d}",
                patient_id=wa_id,
                professional_id=professional.professional_id,
                data_hora=appointment_time,
                duracao_min=30 if number % 5 else 45,
                status=status,
                valor=money(rng, 180, 780),
                observacoes=f"Paciente associado ao fluxo {intent.lower()}.",
            )
        )
        messages.append(
            PatientMessage(
                message_id=f"MSG-{number:06d}",
                wa_id=wa_id,
                telefone=brazilian_phone(rng)
                .replace("(", "")
                .replace(") ", "")
                .replace(" ", ""),
                mensagem=INTENT_MESSAGES[intent][index % len(INTENT_MESSAGES[intent])],
                received_at=received_at,
                rotulo_confirmacao=intent,
                confianca=confianca,
                human_review=human_review,
                appointment_id=f"APT-{number:06d}",
            )
        )
        labels.append(
            PatientMessageLabel(
                id=f"LBL-{number:06d}",
                message_id=f"MSG-{number:06d}",
                intent=intent,
                confianca=confianca,
                reviewed_by="enfermeira.plantao" if human_review else None,
                reviewed_at=next_moment(rng, received_at, min_minutes=5, max_days=2)
                if human_review
                else None,
                origem="HUMANO" if human_review and number % 2 == 0 else "REGRA",
            )
        )
        logs.append(
            WorkflowLog(
                id=f"WFL-{number:06d}",
                appointment_id=f"APT-{number:06d}",
                message_id=f"MSG-{number:06d}",
                acao="classificacao_inicial",
                status_anterior="AGENDADA",
                status_novo=status,
                executed_by="bot" if not human_review else "humano",
                occurred_at=next_moment(rng, received_at, min_minutes=1, max_days=1),
            )
        )

        if intent == "REMARCAR":
            match_slot = next(
                (
                    slot
                    for slot in slots
                    if slot.professional_id == professional.professional_id
                    and slot.disponivel
                ),
                None,
            )
            preference_date = appointment_time + timedelta(days=3)
            waitlist_rows.append(
                Waitlist(
                    id=f"WTL-{number:06d}",
                    patient_id=wa_id,
                    especialidade=professional.especialidade,
                    preferencia_data=preference_date,
                    created_at=min(
                        next_moment(rng, received_at, min_minutes=2, max_days=1),
                        preference_date,
                    ),
                    status="OFERECIDO" if match_slot is not None else "AGUARDANDO",
                    offered_slot_id=match_slot.slot_id
                    if match_slot is not None
                    else None,
                )
            )
            if match_slot is not None:
                match_slot.disponivel = False
                match_slot.reservado_por = wa_id

    db.add_all(professionals)
    db.add_all(messages)
    db.add_all(labels)
    db.add_all(appointments)
    db.add_all(slots)
    db.add_all(waitlist_rows)
    db.add_all(logs)
    db.commit()
    logger.info("Group 10 seeded with %d appointments", len(appointments))
