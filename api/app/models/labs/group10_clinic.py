from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    event,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from ...db.database import Base


MESSAGE_INTENTS = (
    "CONFIRMAR",
    "CANCELAR",
    "REMARCAR",
    "DUVIDA",
    "RECUSA",
    "SAUDACAO",
    "RUIDO",
)
MESSAGE_ORIGINS = ("LLM", "HUMANO", "REGRA")
APPOINTMENT_STATUSES = (
    "AGENDADA",
    "CONFIRMADA",
    "CANCELADA_POR_PACIENTE",
    "REMARCADA",
    "FALTA",
    "REALIZADA",
)
WAITLIST_STATUSES = ("AGUARDANDO", "OFERECIDO", "ACEITO", "EXPIRADO")


class PatientMessage(Base):
    __tablename__ = "lab_g10_patient_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    wa_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    telefone: Mapped[str] = mapped_column(String, nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    rotulo_confirmacao: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    confianca: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    appointment_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )


class PatientMessageLabel(Base):
    __tablename__ = "lab_g10_patient_message_labels"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    message_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    intent: Mapped[str] = mapped_column(String, nullable=False, index=True)
    confianca: Mapped[float] = mapped_column(Float, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    origem: Mapped[str] = mapped_column(String, nullable=False, index=True)


class Professional(Base):
    __tablename__ = "lab_g10_professionals"

    professional_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    especialidade: Mapped[str] = mapped_column(String, nullable=False, index=True)
    registro: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )


class Appointment(Base):
    __tablename__ = "lab_g10_appointments"

    appointment_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    professional_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    duracao_min: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Slot(Base):
    __tablename__ = "lab_g10_slots"

    slot_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    professional_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    disponivel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    reservado_por: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class Waitlist(Base):
    __tablename__ = "lab_g10_waitlist"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    especialidade: Mapped[str] = mapped_column(String, nullable=False, index=True)
    preferencia_data: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    offered_slot_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )


class WorkflowLog(Base):
    __tablename__ = "lab_g10_workflow_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    appointment_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status_anterior: Mapped[str | None] = mapped_column(String, nullable=True)
    status_novo: Mapped[str | None] = mapped_column(String, nullable=True)
    executed_by: Mapped[str] = mapped_column(String, nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


@event.listens_for(Session, "do_orm_execute")
def _ensure_group10_seed_for_direct_secondary_queries(execute_state) -> None:
    if not execute_state.is_select:
        return
    session = execute_state.session
    if session.info.get("_g10_autoseed"):
        return
    entities = {
        description.get("entity")
        for description in getattr(execute_state.statement, "column_descriptions", [])
    }
    if not entities.intersection({Professional, Slot, Waitlist, WorkflowLog}):
        return
    total = int(
        session.execute(select(func.count()).select_from(Professional)).scalar_one()
    )
    if total > 0:
        return
    from ...db.labs_seed.group10 import seed_group

    session.info["_g10_autoseed"] = True
    try:
        seed_group(session)
    finally:
        session.info["_g10_autoseed"] = False


class PatientMessageCreate(BaseModel):
    wa_id: str = Field(
        ...,
        description="Identidade unica do paciente no WhatsApp.",
        examples=["wa-5511999990001"],
    )
    telefone: str = Field(
        ..., description="Telefone do paciente.", examples=["5511999990001"]
    )
    mensagem: str = Field(
        ...,
        description="Mensagem livre recebida no WhatsApp.",
        examples=["Confirmo minha consulta de amanha."],
    )
    appointment_id: str | None = Field(
        default=None,
        description="Consulta vinculada quando existir.",
        examples=["APT-000001"],
    )
    received_at: datetime | None = Field(
        default=None,
        description="Momento de recebimento opcional.",
        examples=["2026-09-13T10:00:00"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "wa_id": "wa-5511999990001",
                    "telefone": "5511999990001",
                    "mensagem": "Confirmo minha consulta de amanha.",
                    "appointment_id": "APT-000001",
                }
            ]
        }
    )


class MessageClassifyRequest(BaseModel):
    intent: str | None = Field(
        default=None,
        description="Intent opcional. Se omitido, usa a classificacao deterministica.",
        examples=["CONFIRMAR"],
    )
    confianca: float | None = Field(
        default=None, description="Confianca opcional entre 0 e 1.", examples=[0.91]
    )
    origem: str = Field(
        default="REGRA",
        description=f"Origem da classificacao: {', '.join(MESSAGE_ORIGINS)}.",
        examples=["REGRA"],
    )
    reviewed_by: str | None = Field(
        default=None,
        description="Preencha quando houver revisao humana.",
        examples=["enfermeira.plantao"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"intent": "CONFIRMAR", "confianca": 0.91, "origem": "REGRA"},
                {
                    "intent": "REMARCAR",
                    "confianca": 0.67,
                    "origem": "HUMANO",
                    "reviewed_by": "atendente.1",
                },
            ]
        }
    )


class WaitlistCreate(BaseModel):
    patient_id: str = Field(
        ..., description="wa_id do paciente.", examples=["wa-5511999990001"]
    )
    especialidade: str = Field(
        ..., description="Especialidade desejada.", examples=["Cardiologia"]
    )
    preferencia_data: datetime = Field(
        ..., description="Horario preferido.", examples=["2026-09-20T10:00:00"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "patient_id": "wa-5511999990001",
                    "especialidade": "Cardiologia",
                    "preferencia_data": "2026-09-20T10:00:00",
                }
            ]
        }
    )


class PatientMessageResponse(BaseModel):
    message_id: str
    wa_id: str
    telefone: str
    mensagem: str
    received_at: datetime
    human_review: bool
    appointment_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PatientMessageInstructorResponse(PatientMessageResponse):
    rotulo_confirmacao: str | None = None
    confianca: float | None = None
    label_intent: str | None = None
    label_confianca: float | None = None


class PatientMessageLabelResponse(BaseModel):
    id: str
    message_id: str
    intent: str
    confianca: float
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    origem: str

    model_config = ConfigDict(from_attributes=True)


class ProfessionalResponse(BaseModel):
    professional_id: str
    nome: str
    especialidade: str
    registro: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    appointment_id: str
    patient_id: str
    professional_id: str
    data_hora: datetime
    duracao_min: int
    status: str
    valor: float
    observacoes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SlotResponse(BaseModel):
    slot_id: str
    professional_id: str
    data_hora: datetime
    disponivel: bool
    reservado_por: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WaitlistResponse(BaseModel):
    id: str
    patient_id: str
    especialidade: str
    preferencia_data: datetime
    created_at: datetime
    status: str
    offered_slot_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowLogResponse(BaseModel):
    id: str
    appointment_id: str
    message_id: str | None = None
    acao: str
    status_anterior: str | None = None
    status_novo: str | None = None
    executed_by: str
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)
