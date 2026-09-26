from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


RECEIVABLE_STATUSES = ("ABERTO", "PAGO", "VENCIDO", "CANCELADO")
COLLECTION_ACTIONS = ("ENVIAR_EMAIL", "ENVIAR_SMS", "LIGAR", "SUSPENDER")
COLLECTION_RESULTS = ("SUCESSO", "FALHA", "IGNORADO")


class Receivable(Base):
    __tablename__ = "lab_g07_receivables"

    id_titulo: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    customer_document: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    customer_phone: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    data_emissao: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    data_vencimento: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    dias_atraso: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    valor_pago: Mapped[float | None] = mapped_column(Float, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    deve_enviar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class CollectionConfig(Base):
    __tablename__ = "lab_g07_collection_configs"

    config_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    faixa_inicio: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    faixa_fim: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    canal: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    template_mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class CollectionHistory(Base):
    __tablename__ = "lab_g07_collection_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    id_titulo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    config_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    canal: Mapped[str] = mapped_column(String, nullable=False, index=True)
    mensagem_enviada: Mapped[str] = mapped_column(Text, nullable=False)
    enviada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    resultado: Mapped[str] = mapped_column(String, nullable=False, index=True)
    respondedido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    motivo: Mapped[str | None] = mapped_column(String, nullable=True)


def faixa_label(dias_atraso: int) -> str:
    if dias_atraso <= 0:
        return "em_dia"
    if dias_atraso <= 15:
        return "1-15"
    if dias_atraso <= 30:
        return "16-30"
    if dias_atraso <= 60:
        return "31-60"
    if dias_atraso <= 90:
        return "61-90"
    return "90+"


class BulkSendRequest(BaseModel):
    faixa: str = Field(..., description="Aging bucket to process: 1-15, 16-30, 31-60, 61-90 or 90+.", examples=["16-30"])
    limit: int = Field(default=100, ge=1, le=500, description="Maximum number of receivables to process in the batch.", examples=[50])

    model_config = ConfigDict(json_schema_extra={"examples": [{"faixa": "16-30", "limit": 50}]})


class WriteOffRequest(BaseModel):
    motivo: str = Field(..., max_length=200, description="Business reason for cancelling the receivable.", examples=["Acordo comercial aprovado"])

    model_config = ConfigDict(json_schema_extra={"examples": [{"motivo": "Acordo comercial aprovado"}]})


class ReceivableResponse(BaseModel):
    id_titulo: str
    customer_id: str
    customer_name: str
    customer_document: str | None = None
    customer_phone: str | None = None
    valor: float
    data_emissao: datetime
    data_vencimento: datetime
    status: str
    dias_atraso: int
    valor_pago: float | None = None
    paid_at: datetime | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReceivableInstructorResponse(ReceivableResponse):
    deve_enviar: bool


class CollectionConfigResponse(BaseModel):
    config_id: str
    faixa_inicio: int
    faixa_fim: int | None = None
    acao: str
    canal: str
    ativo: bool
    template_mensagem: str
    ordem: int

    model_config = ConfigDict(from_attributes=True)


class CollectionHistoryResponse(BaseModel):
    id: str
    id_titulo: str
    config_id: str | None = None
    acao: str
    canal: str
    mensagem_enviada: str
    enviada_em: datetime
    resultado: str
    respondedido: bool
    motivo: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CollectionDecisionResponse(BaseModel):
    receivable: ReceivableResponse
    applicable_config: CollectionConfigResponse | None = None
    history: list[CollectionHistoryResponse]


class BulkSendResult(BaseModel):
    processed: int
    success: int
    failed: int
    ignored: int
    outcomes: list[CollectionHistoryResponse]
