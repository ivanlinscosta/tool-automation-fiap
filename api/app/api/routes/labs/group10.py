from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.deps import (
    InstructorKey,
    LABS_GROUP_PATH,
    LabGroupHeader,
    Scenario,
    entity_not_found,
    require_group,
    require_instructor_key,
    scenario_or_422,
)
from ....labs.generators import LAB_NOW
from ....labs.pagination import apply_sort, build_page, page_params
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group10_clinic import (
    Appointment,
    AppointmentResponse,
    MessageClassifyRequest,
    PatientMessage,
    PatientMessageCreate,
    PatientMessageInstructorResponse,
    PatientMessageLabel,
    PatientMessageLabelResponse,
    PatientMessageResponse,
    Professional,
    ProfessionalResponse,
    Slot,
    SlotResponse,
    Waitlist,
    WaitlistCreate,
    WaitlistResponse,
    WorkflowLog,
    WorkflowLogResponse,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 10"
Group10 = Depends(require_group(10))


def _next_id(db: Session, model: type, field_name: str, prefix: str) -> str:
    field = getattr(model, field_name)
    highest = db.execute(
        select(field).order_by(field.desc()).limit(1)
    ).scalar_one_or_none()
    if highest is None:
        return f"{prefix}-000001"
    return f"{prefix}-{int(str(highest).rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _message_or_404(db: Session, message_id: str) -> PatientMessage:
    row = db.get(PatientMessage, message_id)
    if row is None:
        raise entity_not_found("PatientMessage", message_id)
    return row


def _appointment_or_404(db: Session, appointment_id: str) -> Appointment:
    row = db.get(Appointment, appointment_id)
    if row is None:
        raise entity_not_found("Appointment", appointment_id)
    return row


def _waitlist_or_404(db: Session, waitlist_id: str) -> Waitlist:
    row = db.get(Waitlist, waitlist_id)
    if row is None:
        raise entity_not_found("Waitlist", waitlist_id)
    return row


def _deployment_label(db: Session, message_id: str) -> PatientMessageLabel | None:
    return db.execute(
        select(PatientMessageLabel)
        .where(PatientMessageLabel.message_id == message_id)
        .order_by(PatientMessageLabel.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _classify_message_text(text: str) -> tuple[str, float]:
    normalized = text.lower()
    if any(term in normalized for term in ("confirm", "estarei", "pode manter")):
        return "CONFIRMAR", 0.92
    if any(term in normalized for term in ("cancel", "nao vou", "desmarcar")):
        return "CANCELAR", 0.94
    if any(term in normalized for term in ("remar", "reagend", "trocar o horario")):
        return "REMARCAR", 0.71
    if any(term in normalized for term in ("endereco", "exame", "quanto tempo")):
        return "DUVIDA", 0.81
    if any(term in normalized for term in ("desistir", "nao quero", "recuso")):
        return "RECUSA", 0.88
    if any(term in normalized for term in ("bom dia", "boa tarde", "ola")):
        return "SAUDACAO", 0.79
    return "RUIDO", 0.42


def _human_review_required(
    message: PatientMessage, label: PatientMessageLabel | None
) -> bool:
    return message.human_review and (label is None or label.origem != "HUMANO")


def _log(
    db: Session,
    appointment_id: str,
    message_id: str | None,
    acao: str,
    previous: str | None,
    new: str | None,
    executed_by: str,
) -> None:
    db.add(
        WorkflowLog(
            id=_next_id(db, WorkflowLog, "id", "WFL"),
            appointment_id=appointment_id,
            message_id=message_id,
            acao=acao,
            status_anterior=previous,
            status_novo=new,
            executed_by=executed_by,
            occurred_at=LAB_NOW,
        )
    )


def _free_slot_for_appointment(db: Session, appointment: Appointment) -> Slot | None:
    return db.execute(
        select(Slot)
        .where(
            Slot.professional_id == appointment.professional_id,
            Slot.disponivel.is_(True),
            Slot.data_hora > appointment.data_hora,
        )
        .order_by(Slot.data_hora.asc())
        .limit(1)
    ).scalar_one_or_none()


def _apply_intent(
    db: Session,
    appointment: Appointment,
    intent: str,
    patient_id: str,
    message_id: str | None,
    executed_by: str,
) -> Appointment:
    previous = appointment.status
    if intent == "CONFIRMAR":
        appointment.status = "CONFIRMADA"
        _log(
            db,
            appointment.appointment_id,
            message_id,
            "confirmar",
            previous,
            appointment.status,
            executed_by,
        )
        return appointment
    if intent in {"CANCELAR", "RECUSA"}:
        appointment.status = "CANCELADA_POR_PACIENTE"
        _log(
            db,
            appointment.appointment_id,
            message_id,
            "cancelar",
            previous,
            appointment.status,
            executed_by,
        )
        return appointment
    if intent == "REMARCAR":
        slot = _free_slot_for_appointment(db, appointment)
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No free slot available for reschedule",
            )
        slot.disponivel = False
        slot.reservado_por = patient_id
        appointment.status = "REMARCADA"
        db.add(
            Waitlist(
                id=_next_id(db, Waitlist, "id", "WTL"),
                patient_id=patient_id,
                especialidade=db.get(
                    Professional, appointment.professional_id
                ).especialidade,
                preferencia_data=slot.data_hora,
                created_at=LAB_NOW,
                status="OFERECIDO",
                offered_slot_id=slot.slot_id,
            )
        )
        _log(
            db,
            appointment.appointment_id,
            message_id,
            "remarcar",
            previous,
            appointment.status,
            executed_by,
        )
        return appointment
    _log(
        db,
        appointment.appointment_id,
        message_id,
        "registrar_intencao",
        previous,
        previous,
        executed_by,
    )
    return appointment



@router.get(
    f"{PREFIX}/patient-messages",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_list_messages",
    summary="List patient messages",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_messages(
    scenario: Scenario = None,
    group: LabGroup = Group10,
    intent: str | None = Query(default=None),
    human_review: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default="message_id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(PatientMessage)
    if intent:
        query = query.join(
            PatientMessageLabel,
            PatientMessageLabel.message_id == PatientMessage.message_id,
        ).where(PatientMessageLabel.intent == intent)
    if human_review is not None:
        query = query.where(PatientMessage.human_review.is_(human_review))
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(PatientMessage.mensagem).like(pattern),
                func.lower(PatientMessage.telefone).like(pattern),
                func.lower(PatientMessage.wa_id).like(pattern),
            )
        )
    query = apply_sort(query, PatientMessage, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: PatientMessageResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/patient-messages/{{message_id}}",
    response_model=PatientMessageResponse,
    tags=[TAG],
    operation_id="labs_group10_get_message",
    summary="Get one message",
    responses={
        404: {"description": "Message not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def get_message(
    message_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PatientMessageResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return PatientMessageResponse.model_validate(_message_or_404(db, message_id))


@router.get(
    f"{PREFIX}/appointments",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_list_appointments",
    summary="List clinic appointments",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_appointments(
    scenario: Scenario = None,
    group: LabGroup = Group10,
    status_filter: str | None = Query(default=None, alias="status"),
    professional: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default="appointment_id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Appointment)
    if status_filter:
        query = query.where(Appointment.status == status_filter)
    if professional:
        query = query.where(Appointment.professional_id == professional)
    if start_at:
        query = query.where(Appointment.data_hora >= start_at)
    if end_at:
        query = query.where(Appointment.data_hora <= end_at)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Appointment.patient_id).like(pattern),
                func.lower(Appointment.observacoes).like(pattern),
            )
        )
    query = apply_sort(query, Appointment, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: AppointmentResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/appointments/{{appointment_id}}",
    response_model=AppointmentResponse,
    tags=[TAG],
    operation_id="labs_group10_get_appointment",
    summary="Get one appointment",
    responses={
        404: {"description": "Appointment not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def get_appointment(
    appointment_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> AppointmentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return AppointmentResponse.model_validate(_appointment_or_404(db, appointment_id))


@router.get(
    f"{PREFIX}/professionals",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_list_professionals",
    summary="List healthcare professionals",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_professionals(
    scenario: Scenario = None,
    group: LabGroup = Group10,
    ativo: bool | None = Query(default=None),
    sort: str | None = Query(default="professional_id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Professional)
    if ativo is not None:
        query = query.where(Professional.ativo.is_(ativo))
    query = apply_sort(query, Professional, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: ProfessionalResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/slots",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_list_slots",
    summary="List appointment slots",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_slots(
    scenario: Scenario = None,
    group: LabGroup = Group10,
    professional: str | None = Query(default=None),
    disponivel: bool | None = Query(default=None),
    date: datetime | None = Query(default=None),
    sort: str | None = Query(default="slot_id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Slot)
    if professional:
        query = query.where(Slot.professional_id == professional)
    if disponivel is not None:
        query = query.where(Slot.disponivel.is_(disponivel))
    if date:
        query = query.where(Slot.data_hora >= date)
    query = apply_sort(query, Slot, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: SlotResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/waitlist",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_list_waitlist",
    summary="List waitlist entries",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_waitlist(
    scenario: Scenario = None,
    group: LabGroup = Group10,
    patient_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Waitlist)
    if patient_id:
        query = query.where(Waitlist.patient_id == patient_id)
    if status_filter:
        query = query.where(Waitlist.status == status_filter)
    query = apply_sort(query, Waitlist, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: WaitlistResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/workflow-logs",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_list_workflow_logs",
    summary="List workflow logs",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_workflow_logs(
    scenario: Scenario = None,
    group: LabGroup = Group10,
    appointment_id: str | None = Query(default=None),
    message_id: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(WorkflowLog)
    if appointment_id:
        query = query.where(WorkflowLog.appointment_id == appointment_id)
    if message_id:
        query = query.where(WorkflowLog.message_id == message_id)
    query = apply_sort(query, WorkflowLog, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: WorkflowLogResponse.model_validate(row).model_dump(),
    )


@router.post(
    f"{PREFIX}/patient-messages",
    response_model=PatientMessageResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group10_create_message",
    summary="Ingest a WhatsApp message",
    responses={
        404: {"description": "Appointment not found"},
        409: {"description": "Duplicate wa_id"},
        422: {"description": "Validation error"},
    },
)
async def create_message(
    payload: PatientMessageCreate,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PatientMessageResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if (
        db.execute(
            select(PatientMessage).where(PatientMessage.wa_id == payload.wa_id)
        ).scalar_one_or_none()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="wa_id already exists"
        )
    if payload.appointment_id is not None:
        _appointment_or_404(db, payload.appointment_id)
    intent, confidence = _classify_message_text(payload.mensagem)
    message = PatientMessage(
        message_id=_next_id(db, PatientMessage, "message_id", "MSG"),
        wa_id=payload.wa_id,
        telefone=payload.telefone,
        mensagem=payload.mensagem,
        received_at=payload.received_at or LAB_NOW,
        rotulo_confirmacao=intent,
        confianca=confidence,
        human_review=confidence < 0.75,
        appointment_id=payload.appointment_id,
    )
    db.add(message)
    db.add(
        PatientMessageLabel(
            id=_next_id(db, PatientMessageLabel, "id", "LBL"),
            message_id=message.message_id,
            intent=intent,
            confianca=confidence,
            reviewed_by=None,
            reviewed_at=None,
            origem="REGRA",
        )
    )
    db.commit()
    create_event(
        db,
        "lab_group10_message_created",
        x_lab_group,
        "patient_message",
        message.message_id,
        {"group": "10"},
    )
    return PatientMessageResponse.model_validate(message)


@router.post(
    f"{PREFIX}/patient-messages/{{message_id}}/classify",
    response_model=PatientMessageLabelResponse,
    tags=[TAG],
    operation_id="labs_group10_classify_message",
    summary="Classify or review one message",
    responses={
        404: {"description": "Message not found"},
        422: {"description": "Validation error"},
    },
)
async def classify_message(
    message_id: str,
    payload: MessageClassifyRequest,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PatientMessageLabelResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    message = _message_or_404(db, message_id)
    intent, confidence = _classify_message_text(message.mensagem)
    if payload.intent is not None:
        intent = payload.intent
    if payload.confianca is not None:
        confidence = payload.confianca
    message.rotulo_confirmacao = intent
    message.confianca = confidence
    message.human_review = confidence < 0.75 and payload.origem != "HUMANO"
    label = PatientMessageLabel(
        id=_next_id(db, PatientMessageLabel, "id", "LBL"),
        message_id=message.message_id,
        intent=intent,
        confianca=confidence,
        reviewed_by=payload.reviewed_by,
        reviewed_at=LAB_NOW if payload.reviewed_by else None,
        origem=payload.origem,
    )
    db.add(label)
    db.commit()
    create_event(
        db,
        "lab_group10_message_classified",
        x_lab_group,
        "patient_message",
        message.message_id,
        {"group": "10", "intent": intent},
    )
    return PatientMessageLabelResponse.model_validate(label)


@router.post(
    f"{PREFIX}/patient-messages/{{message_id}}/apply",
    response_model=AppointmentResponse,
    tags=[TAG],
    operation_id="labs_group10_apply_message",
    summary="Apply message intent to the linked appointment",
    responses={
        404: {"description": "Message or appointment not found"},
        409: {"description": "Human review required or no free slot"},
        422: {"description": "Invalid scenario"},
    },
)
async def apply_message(
    message_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> AppointmentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    message = _message_or_404(db, message_id)
    if not message.appointment_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message has no linked appointment",
        )
    label = _deployment_label(db, message_id)
    if _human_review_required(message, label):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Human review is required before applying this message",
        )
    appointment = _appointment_or_404(db, message.appointment_id)
    intent = (
        label.intent if label is not None else message.rotulo_confirmacao or "RUIDO"
    )
    _apply_intent(
        db,
        appointment,
        intent,
        message.wa_id,
        message.message_id,
        "bot" if label is None or label.origem != "HUMANO" else "humano",
    )
    db.commit()
    create_event(
        db,
        "lab_group10_message_applied",
        x_lab_group,
        "appointment",
        appointment.appointment_id,
        {"group": "10", "message_id": message.message_id},
    )
    return AppointmentResponse.model_validate(appointment)


@router.get(
    f"{PREFIX}/patient-messages/{{message_id}}/history",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_message_history",
    summary="Get workflow history for one message",
    responses={
        404: {"description": "Message not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def message_history(
    message_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    _message_or_404(db, message_id)
    rows = list(
        db.execute(
            select(WorkflowLog)
            .where(WorkflowLog.message_id == message_id)
            .order_by(WorkflowLog.occurred_at.asc())
        )
        .scalars()
        .all()
    )
    return {
        "items": [WorkflowLogResponse.model_validate(row).model_dump() for row in rows],
        "meta": {"total": len(rows)},
    }


@router.post(
    f"{PREFIX}/appointments/{{appointment_id}}/confirm",
    response_model=AppointmentResponse,
    tags=[TAG],
    operation_id="labs_group10_confirm_appointment",
    summary="Confirm an appointment",
    responses={
        404: {"description": "Appointment not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def confirm_appointment(
    appointment_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> AppointmentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    appointment = _appointment_or_404(db, appointment_id)
    _apply_intent(db, appointment, "CONFIRMAR", appointment.patient_id, None, "humano")
    db.commit()
    create_event(
        db,
        "lab_group10_appointment_confirmed",
        x_lab_group,
        "appointment",
        appointment_id,
        {"group": "10"},
    )
    return AppointmentResponse.model_validate(appointment)


@router.post(
    f"{PREFIX}/appointments/{{appointment_id}}/cancel",
    response_model=AppointmentResponse,
    tags=[TAG],
    operation_id="labs_group10_cancel_appointment",
    summary="Cancel an appointment",
    responses={
        404: {"description": "Appointment not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def cancel_appointment(
    appointment_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> AppointmentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    appointment = _appointment_or_404(db, appointment_id)
    _apply_intent(db, appointment, "CANCELAR", appointment.patient_id, None, "humano")
    db.commit()
    create_event(
        db,
        "lab_group10_appointment_cancelled",
        x_lab_group,
        "appointment",
        appointment_id,
        {"group": "10"},
    )
    return AppointmentResponse.model_validate(appointment)


@router.post(
    f"{PREFIX}/appointments/{{appointment_id}}/reschedule",
    response_model=AppointmentResponse,
    tags=[TAG],
    operation_id="labs_group10_reschedule_appointment",
    summary="Reschedule an appointment",
    responses={
        404: {"description": "Appointment not found"},
        409: {"description": "No free slot available"},
        422: {"description": "Invalid scenario"},
    },
)
async def reschedule_appointment(
    appointment_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> AppointmentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    appointment = _appointment_or_404(db, appointment_id)
    _apply_intent(db, appointment, "REMARCAR", appointment.patient_id, None, "humano")
    db.commit()
    create_event(
        db,
        "lab_group10_appointment_rescheduled",
        x_lab_group,
        "appointment",
        appointment_id,
        {"group": "10"},
    )
    return AppointmentResponse.model_validate(appointment)


@router.post(
    f"{PREFIX}/waitlist",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group10_create_waitlist",
    summary="Join the waitlist",
    responses={
        404: {"description": "Patient not found"},
        422: {"description": "Validation error"},
    },
)
async def create_waitlist(
    payload: WaitlistCreate,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> WaitlistResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if (
        db.execute(
            select(PatientMessage).where(PatientMessage.wa_id == payload.patient_id)
        ).scalar_one_or_none()
        is None
    ):
        raise entity_not_found("PatientMessage.wa_id", payload.patient_id)
    row = Waitlist(
        id=_next_id(db, Waitlist, "id", "WTL"),
        patient_id=payload.patient_id,
        especialidade=payload.especialidade,
        preferencia_data=payload.preferencia_data,
        created_at=LAB_NOW,
        status="AGUARDANDO",
        offered_slot_id=None,
    )
    db.add(row)
    db.commit()
    create_event(
        db,
        "lab_group10_waitlist_joined",
        x_lab_group,
        "waitlist",
        row.id,
        {"group": "10"},
    )
    return WaitlistResponse.model_validate(row)


@router.post(
    f"{PREFIX}/waitlist/{{waitlist_id}}/offer",
    response_model=WaitlistResponse,
    tags=[TAG],
    operation_id="labs_group10_offer_waitlist",
    summary="Offer a free slot to a waitlist entry",
    responses={
        404: {"description": "Waitlist not found"},
        409: {"description": "No free slot available"},
        422: {"description": "Invalid scenario"},
    },
)
async def offer_waitlist(
    waitlist_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> WaitlistResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    row = _waitlist_or_404(db, waitlist_id)
    professional_ids = [
        item.professional_id
        for item in db.execute(
            select(Professional).where(Professional.especialidade == row.especialidade)
        )
        .scalars()
        .all()
    ]
    slot = db.execute(
        select(Slot)
        .where(
            Slot.professional_id.in_(professional_ids),
            Slot.disponivel.is_(True),
            Slot.data_hora >= row.preferencia_data,
        )
        .order_by(Slot.data_hora.asc())
        .limit(1)
    ).scalar_one_or_none()
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No free slot available for waitlist offer",
        )
    slot.disponivel = False
    slot.reservado_por = row.patient_id
    row.status = "OFERECIDO"
    row.offered_slot_id = slot.slot_id
    db.commit()
    create_event(
        db,
        "lab_group10_waitlist_offered",
        x_lab_group,
        "waitlist",
        row.id,
        {"group": "10", "slot_id": slot.slot_id},
    )
    return WaitlistResponse.model_validate(row)


@router.get(
    f"{PREFIX}/instructor/patient-messages/{{message_id}}",
    response_model=PatientMessageInstructorResponse,
    tags=[TAG],
    operation_id="labs_group10_instructor_get_message",
    summary="Instructor only: get hidden message classification fields",
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled"},
        404: {"description": "Message not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def instructor_get_message(
    message_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PatientMessageInstructorResponse:
    await apply_scenario(scenario_or_422(scenario))
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    message = _message_or_404(db, message_id)
    label = _deployment_label(db, message_id)
    body = PatientMessageInstructorResponse.model_validate(message).model_dump()
    body["label_intent"] = label.intent if label is not None else None
    body["label_confianca"] = label.confianca if label is not None else None
    return PatientMessageInstructorResponse(**body)


@router.get(
    f"{PREFIX}/clinic-stats",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group10_stats",
    summary="Get clinic aggregates",
    responses={422: {"description": "Invalid scenario"}},
)
async def get_stats(
    scenario: Scenario = None,
    group: LabGroup = Group10,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    messages = list(db.execute(select(PatientMessage)).scalars().all())
    appointments = list(db.execute(select(Appointment)).scalars().all())
    labels = list(db.execute(select(PatientMessageLabel)).scalars().all())
    return {
        "messages": len(messages),
        "appointments": len(appointments),
        "by_intent": {
            value: sum(1 for row in labels if row.intent == value)
            for value in sorted({row.intent for row in labels})
        },
        "by_status": {
            value: sum(1 for row in appointments if row.status == value)
            for value in sorted({row.status for row in appointments})
        },
        "human_review": {
            "required": sum(1 for row in messages if row.human_review),
            "not_required": sum(1 for row in messages if not row.human_review),
        },
    }
