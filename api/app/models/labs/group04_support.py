from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


EVENT_STATUSES = ("novo", "roteado", "em_atendimento", "resolvido")
EVENT_PRIORITIES = ("P1", "P2", "P3", "P4")
EVENT_INTENTS = (
    "cancelamento",
    "troca",
    "duvida_produto",
    "reclamacao",
    "elogio",
    "reclamacao_financ",
    "upgrade",
)
LEVELS = ("alto", "medio", "baixo")


class Department(Base):
    __tablename__ = "lab_g04_departments"

    department_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    sla_horas_padrao: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )


class CustomerEvent(Base):
    __tablename__ = "lab_g04_customer_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    canal: Mapped[str] = mapped_column(String, nullable=False, index=True)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    intencao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    prioridade: Mapped[str] = mapped_column(String, nullable=False, index=True)
    confianca: Mapped[float] = mapped_column(Float, nullable=False)
    sla_horas: Mapped[int] = mapped_column(Integer, nullable=False)
    departamento: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    impacto: Mapped[str] = mapped_column(String, nullable=False, index=True)
    urgencia: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="novo", index=True
    )


class CustomerEventCreate(BaseModel):
    customer_id: str = Field(
        ...,
        max_length=80,
        description="Customer identifier reported by the intake channel.",
        examples=["CUS-LAB-04001"],
    )
    canal: str = Field(
        ...,
        max_length=40,
        description=(
            "Inbound channel. Must match the deterministic channel catalog used "
            "by the lab."
        ),
        examples=["whatsapp"],
    )
    mensagem: str = Field(
        ...,
        min_length=10,
        max_length=4000,
        description=(
            "Original customer message used for deterministic intent classification."
        ),
        examples=["Quero cancelar minha assinatura antes da renovacao."],
    )
    impacto: str = Field(
        ...,
        max_length=10,
        description=(
            "Business impact level: alto, medio or baixo. Priority is computed "
            "from intent plus impact and urgency."
        ),
        examples=["alto"],
    )
    urgencia: str = Field(
        ...,
        max_length=10,
        description=(
            "Response urgency: alto, medio or baixo. P1 requires at least one "
            "dimension alto plus a sensitive intent such as cancelamento or "
            "reclamacao_financ."
        ),
        examples=["alto"],
    )
    created_at: datetime | None = Field(
        default=None,
        description=(
            "Optional deterministic timestamp; defaults to the lab reference instant."
        ),
        examples=["2026-09-13T09:00:00"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "customer_id": "CUS-LAB-04001",
                    "canal": "whatsapp",
                    "mensagem": "Quero cancelar minha assinatura antes da renovacao.",
                    "impacto": "alto",
                    "urgencia": "alto",
                }
            ]
        }
    )


class CustomerEventRoute(BaseModel):
    departamento: str = Field(
        ...,
        max_length=80,
        description="Active department_id that will own the event after triage.",
        examples=["DEP-01"],
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"departamento": "DEP-01"}]}
    )


class CustomerEventResolve(BaseModel):
    status: str = Field(
        default="resolvido",
        max_length=40,
        description="Final status applied to the event when resolution is complete.",
        examples=["resolvido"],
    )
    resolved_at: datetime | None = Field(
        default=None,
        description=(
            "Optional deterministic resolution timestamp; defaults to the lab "
            "reference instant."
        ),
        examples=["2026-09-13T18:00:00"],
    )

    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "resolvido"}]})


class DepartmentResponse(BaseModel):
    department_id: str
    nome: str
    descricao: str
    sla_horas_padrao: int
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class CustomerEventResponse(BaseModel):
    event_id: str
    customer_id: str
    canal: str
    mensagem: str
    prioridade: str
    sla_horas: int
    departamento: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class CustomerEventInstructorResponse(CustomerEventResponse):
    intencao: str
    confianca: float
    impacto: str
    urgencia: str


class CustomerEventStatsRow(BaseModel):
    canal: str
    intencao: str
    prioridade: str
    total: int
