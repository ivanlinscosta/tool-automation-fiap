from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


CONTRACT_STATUSES = ("ATIVO", "SUSPENSO", "CANCELADO")
INVOICE_STATUSES = ("ABERTA", "PAGA", "VENCIDA")
CREDIT_RESULTS = ("APROVADO", "REJEITADO", "ANALISE_MANUAL")
UNLOCK_REQUEST_STATUSES = ("RECEBIDO", "EM_ANALISE", "APROVADO", "REJEITADO", "AGUARDANDO_PROMESSA")
UNLOCK_DECISIONS = ("LIBERADO", "NEGADO", "PARCIAL")


class CustomerContract(Base):
    __tablename__ = "lab_g08_customer_contracts"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    contract_status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    monthly_value: Mapped[float] = mapped_column(Float, nullable=False)
    pending_invoices: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class Invoice(Base):
    __tablename__ = "lab_g08_invoices"

    invoice_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    data_emissao: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    data_vencimento: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class CreditCheck(Base):
    __tablename__ = "lab_g08_credit_checks"

    check_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    limite_credito: Mapped[float] = mapped_column(Float, nullable=False)
    usado: Mapped[float] = mapped_column(Float, nullable=False)
    disponivel: Mapped[float] = mapped_column(Float, nullable=False)
    data_consulta: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    resultado: Mapped[str] = mapped_column(String, nullable=False, index=True)


class UnlockRequest(Base):
    __tablename__ = "lab_g08_unlock_requests"

    request_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    promessa_pagamento_data: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    decision_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    decisao_esperada: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class UnlockHistory(Base):
    __tablename__ = "lab_g08_unlock_history"

    history_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    acao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status_anterior: Mapped[str | None] = mapped_column(String, nullable=True)
    status_novo: Mapped[str | None] = mapped_column(String, nullable=True)
    executed_by: Mapped[str] = mapped_column(String, nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class UnlockDecision(Base):
    __tablename__ = "lab_g08_unlock_decisions"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    request_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String, nullable=False, index=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    credit_check_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    score_usado: Mapped[int | None] = mapped_column(Integer, nullable=True)


def expected_unlock_decision(
    *,
    contract_status: str,
    pending_invoices: int,
    score: int,
    promise_date: date | None,
    today: date,
) -> tuple[str, str]:
    if contract_status == "CANCELADO":
        return "NEGADO", "Contrato cancelado nao pode ser desbloqueado em confianca."
    if score >= 700 and pending_invoices <= 2:
        return "LIBERADO", "Score forte e baixa inadimplencia permitem o desbloqueio."
    if promise_date is not None and promise_date >= today and promise_date <= today + timedelta(days=5):
        if score >= 520 and pending_invoices <= 4:
            return "LIBERADO", "Promessa de pagamento valida com risco controlado autoriza o desbloqueio."
        if score >= 420 and pending_invoices <= 6:
            return "PARCIAL", "Promessa de pagamento valida, mas o risco exige liberacao parcial."
    return "NEGADO", "Risco de credito ou inadimplencia acima do tolerado para desbloqueio."


class UnlockRequestCreate(BaseModel):
    customer_id: str = Field(..., max_length=40, description="Customer contract identifier.", examples=["UC-000123"])
    motivo: str = Field(..., max_length=2000, description="Free-text reason for the unblock request.", examples=["Cliente informou que pagara amanha e precisa reativar o servico hoje."])

    model_config = ConfigDict(json_schema_extra={"examples": [{"customer_id": "UC-000123", "motivo": "Cliente informou que pagara amanha e precisa reativar o servico hoje."}]})


class PromiseCreate(BaseModel):
    promessa_pagamento_data: date = Field(..., description="Promise-to-pay date. Past dates are rejected.", examples=["2026-09-15"])

    model_config = ConfigDict(json_schema_extra={"examples": [{"promessa_pagamento_data": "2026-09-15"}]})


class DecisionActor(BaseModel):
    executed_by: str = Field(default="analista.lab", max_length=120, description="Mock analyst or automation user applying the action.", examples=["analista.lab"])

    model_config = ConfigDict(json_schema_extra={"examples": [{"executed_by": "analista.lab"}]})


class CustomerContractResponse(BaseModel):
    customer_id: str
    customer_name: str
    contract_status: str
    data_inicio: date
    data_fim: date | None = None
    monthly_value: float
    pending_invoices: int

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    invoice_id: str
    customer_id: str
    valor: float
    data_emissao: datetime
    data_vencimento: datetime
    status: str
    paid_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CreditCheckResponse(BaseModel):
    check_id: str
    customer_id: str
    score: int
    limite_credito: float
    usado: float
    disponivel: float
    data_consulta: datetime
    resultado: str

    model_config = ConfigDict(from_attributes=True)


class UnlockDecisionResponse(BaseModel):
    decision_id: str
    request_id: str
    decision: str
    justification: str
    decided_at: datetime
    credit_check_id: str | None = None
    score_usado: int | None = None

    model_config = ConfigDict(from_attributes=True)


class UnlockRequestResponse(BaseModel):
    request_id: str
    customer_id: str
    protocol: str
    motivo: str
    status: str
    requested_at: datetime
    resolved_at: datetime | None = None
    promessa_pagamento_data: date | None = None
    decision_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UnlockRequestInstructorResponse(UnlockRequestResponse):
    decisao_esperada: str | None = None


class UnlockHistoryResponse(BaseModel):
    history_id: str
    customer_id: str
    request_id: str
    acao: str
    status_anterior: str | None = None
    status_novo: str | None = None
    executed_by: str
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractSummaryResponse(BaseModel):
    contract: CustomerContractResponse
    invoices: list[InvoiceResponse]
    latest_credit_check: CreditCheckResponse | None = None


class UnlockStatsResponse(BaseModel):
    requests_by_status: dict[str, int]
    decisions_by_type: dict[str, int]
