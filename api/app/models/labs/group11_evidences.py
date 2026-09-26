from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


RESULTADOS_RESTORE = ("SUCESSO", "PARCIAL", "FALHA")
SEVERIDADES = ("ALTA", "MEDIA", "BAIXA")
REGISTRY_STATUSES = ("PENDENTE", "EM_ANALISE", "APROVADO", "REPROVADO")
ACTION_PLAN_STATUSES = ("PENDENTE", "EM_ANDAMENTO", "CONCLUIDA", "CANCELADA")


class IncomingEmail(Base):
    __tablename__ = "lab_g11_incoming_emails"

    email_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    remetente: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assunto: Mapped[str] = mapped_column(String, nullable=False, index=True)
    corpo: Mapped[str] = mapped_column(Text, nullable=False)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ticket_mudanca: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severidade: Mapped[str] = mapped_column(String, nullable=False, index=True)


class RestoreEvidence(Base):
    __tablename__ = "lab_g11_restore_evidences"

    evidence_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    email_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    IC: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    data_hora_teste: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    resultado: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sistema: Mapped[str] = mapped_column(String, nullable=False, index=True)
    versao_antes: Mapped[str] = mapped_column(String, nullable=False)
    versao_depois: Mapped[str | None] = mapped_column(String, nullable=True)
    duracao_seg: Mapped[int] = mapped_column(Integer, nullable=False)
    responsavel: Mapped[str] = mapped_column(String, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_prints: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    divergent_fields_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    missing_fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    decisao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)


class EvidenceRegistry(Base):
    __tablename__ = "lab_g11_evidence_registry"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    IC: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    analisado_por: Mapped[str | None] = mapped_column(String, nullable=True)
    analisado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parecer: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActionPlan(Base):
    __tablename__ = "lab_g11_action_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    evidence_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    acao: Mapped[str] = mapped_column(Text, nullable=False)
    prazo: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    responsavel: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    conclusao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class IncomingEmailCreate(BaseModel):
    remetente: str = Field(
        ..., description="Remetente do email.", examples=["ops.restore@example.com"]
    )
    assunto: str = Field(
        ...,
        description="Assunto do email.",
        examples=["Solicitacao de evidencia de restore CHG-1001"],
    )
    corpo: str = Field(
        ...,
        description="Corpo livre do email.",
        examples=[
            "Favor anexar a evidencia do restore executado no ambiente produtivo."
        ],
    )
    recebido_em: datetime | None = Field(
        default=None,
        description="Momento de recebimento opcional.",
        examples=["2026-09-13T08:00:00"],
    )
    ticket_mudanca: str = Field(
        ..., description="Ticket de mudanca associado.", examples=["CHG-1001"]
    )
    severidade: str = Field(
        ..., description=f"Uma de: {', '.join(SEVERIDADES)}.", examples=["ALTA"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "remetente": "ops.restore@example.com",
                    "assunto": "Solicitacao de evidencia de restore CHG-1001",
                    "corpo": (
                        "Favor anexar a evidencia do restore executado "
                        "no ambiente produtivo."
                    ),
                    "ticket_mudanca": "CHG-1001",
                    "severidade": "ALTA",
                }
            ]
        }
    )


class RestoreEvidenceCreate(BaseModel):
    IC: str = Field(
        ...,
        description="Identificador de configuracao da evidencia.",
        examples=["IC-000001"],
    )
    data_hora_teste: datetime = Field(
        ..., description="Data e hora do teste.", examples=["2026-09-13T09:30:00"]
    )
    resultado: str = Field(
        ...,
        description=f"Um de: {', '.join(RESULTADOS_RESTORE)}.",
        examples=["SUCESSO"],
    )
    sistema: str = Field(..., description="Sistema restaurado.", examples=["erp"])
    versao_antes: str = Field(
        ..., description="Versao anterior ao restore.", examples=["1.8.2"]
    )
    versao_depois: str | None = Field(
        default=None, description="Versao apos restore.", examples=["1.8.3"]
    )
    duracao_seg: int = Field(..., description="Duracao em segundos.", examples=[640])
    responsavel: str = Field(
        ..., description="Responsavel pelo teste.", examples=["analista.restore"]
    )
    observacoes: str | None = Field(
        default=None,
        description="Observacoes livres.",
        examples=["Restore executado com sucesso e sem alarmes."],
    )
    has_prints: bool = Field(
        default=False, description="Indica se ha prints anexados.", examples=[True]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "IC": "IC-000001",
                    "data_hora_teste": "2026-09-13T09:30:00",
                    "resultado": "SUCESSO",
                    "sistema": "erp",
                    "versao_antes": "1.8.2",
                    "versao_depois": "1.8.3",
                    "duracao_seg": 640,
                    "responsavel": "analista.restore",
                    "observacoes": "Restore executado com sucesso e sem alarmes.",
                    "has_prints": True,
                }
            ]
        }
    )


class EvidenceReviewRequest(BaseModel):
    status: str = Field(
        ...,
        description=f"Um de: {', '.join(REGISTRY_STATUSES)}.",
        examples=["APROVADO"],
    )
    analisado_por: str = Field(
        ..., description="Quem analisou a evidencia.", examples=["gestor.mudancas"]
    )
    parecer: str | None = Field(
        default=None,
        description="Parecer livre.",
        examples=["Evidencia consistente com o procedimento executado."],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "APROVADO",
                    "analisado_por": "gestor.mudancas",
                    "parecer": "Evidencia consistente.",
                }
            ]
        }
    )


class ActionPlanCreate(BaseModel):
    acao: str = Field(
        ...,
        description="Acao corretiva ou preventiva.",
        examples=["Atualizar runbook com o passo ausente."],
    )
    prazo: date = Field(..., description="Prazo da acao.", examples=["2026-09-20"])
    responsavel: str = Field(
        ..., description="Responsavel pela acao.", examples=["owner.sistema"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "acao": "Atualizar runbook com o passo ausente.",
                    "prazo": "2026-09-20",
                    "responsavel": "owner.sistema",
                }
            ]
        }
    )


class ActionPlanCompleteRequest(BaseModel):
    conclusao: str = Field(
        ...,
        description="Texto final de conclusao.",
        examples=["Runbook atualizado e homologado pelo time."],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"conclusao": "Runbook atualizado e homologado pelo time."}]
        }
    )


class IncomingEmailResponse(BaseModel):
    email_id: str
    remetente: str
    assunto: str
    corpo: str
    recebido_em: datetime
    ticket_mudanca: str
    severidade: str

    model_config = ConfigDict(from_attributes=True)


class RestoreEvidenceResponse(BaseModel):
    evidence_id: str
    email_id: str
    IC: str
    data_hora_teste: datetime
    resultado: str
    sistema: str
    versao_antes: str
    versao_depois: str | None = None
    duracao_seg: int
    responsavel: str
    observacoes: str | None = None
    has_prints: bool

    model_config = ConfigDict(from_attributes=True)


class EvidenceRegistryResponse(BaseModel):
    id: str
    IC: str
    status: str
    analisado_por: str | None = None
    analisado_em: datetime | None = None
    parecer: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ActionPlanResponse(BaseModel):
    id: str
    evidence_id: str
    acao: str
    prazo: date
    responsavel: str
    status: str
    conclusao: str | None = None
    created_at: datetime
    concluded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceAnalysisResponse(BaseModel):
    evidence_id: str
    IC: str
    has_prints: bool
    divergent_fields: list[str]
    missing_fields: list[str]


class EvidenceInstructorResponse(RestoreEvidenceResponse):
    decisao: str
    rationale: str
    divergent_fields: list[str]
    missing_fields: list[str]
