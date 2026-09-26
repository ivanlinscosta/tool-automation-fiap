from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


MESSAGE_INTENTIONS = (
    "troca_produto",
    "defeito_produto",
    "rastreio_pedido",
    "fatura_segunda_via",
    "reclamacao_atraso",
    "duvida_uso",
)

ORDER_STATUSES = ("confirmado", "separado", "enviado", "entregue", "cancelado")
SHIPMENT_STATUSES = ("coletado", "em_transito", "entregue", "extraviado")
TICKET_PRIORITIES = ("baixa", "media", "alta", "critica")
TICKET_STATUSES = ("ABERTO", "EM_ATENDIMENTO", "AGUARDANDO_IDENTIFICACAO", "RESPONDIDO")


class Customer(Base):
    __tablename__ = "lab_g05_customers"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cpf: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    telefone: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Order(Base):
    __tablename__ = "lab_g05_orders"

    order_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    valor_total: Mapped[float] = mapped_column(Float, nullable=False)
    data_pedido: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Shipment(Base):
    __tablename__ = "lab_g05_shipments"

    shipment_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    order_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    codigo_rastreio: Mapped[str] = mapped_column(String, nullable=False, index=True)
    transportadora: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_envio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    data_entrega_prevista: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    data_entrega_real: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Message(Base):
    __tablename__ = "lab_g05_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    cpf_informado: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    telefone_informado: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    email_informado: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    intencao: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class ResponseTemplate(Base):
    __tablename__ = "lab_g05_response_templates"

    template_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    intencao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class Ticket(Base):
    __tablename__ = "lab_g05_tickets"

    ticket_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    message_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    prioridade: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sla_horas: Mapped[int] = mapped_column(Integer, nullable=False)
    resposta_template_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


INTENT_PRIORITY = {
    "troca_produto": ("media", 24),
    "defeito_produto": ("alta", 8),
    "rastreio_pedido": ("media", 12),
    "fatura_segunda_via": ("baixa", 24),
    "reclamacao_atraso": ("alta", 6),
    "duvida_uso": ("baixa", 48),
}


def ticket_priority_for(intencao: str, *, has_order: bool) -> tuple[str, int]:
    prioridade, sla_horas = INTENT_PRIORITY[intencao]
    if not has_order and prioridade == "alta":
        return "media", max(sla_horas, 12)
    if not has_order and prioridade == "baixa":
        return "media", 24
    return prioridade, sla_horas


class MessageCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=160, description="Customer name informed in the contact.", examples=["Marina Costa"])
    cpf: str | None = Field(default=None, max_length=20, description="CPF informed by the customer for identification.", examples=["123.456.789-09"])
    telefone: str | None = Field(default=None, max_length=30, description="Customer phone for lookup when CPF is missing.", examples=["(11) 98877-6655"])
    email: str | None = Field(default=None, max_length=160, description="Optional e-mail informed by the customer.", examples=["marina@example.com"])
    texto: str = Field(..., max_length=4000, description="Free-text post-sale message sent by the customer.", examples=["Meu pedido atrasou e quero saber onde esta a entrega."])

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "customer_name": "Marina Costa",
                    "cpf": "123.456.789-09",
                    "telefone": "(11) 98877-6655",
                    "email": "marina@example.com",
                    "texto": "Meu pedido atrasou e quero saber onde esta a entrega.",
                }
            ]
        }
    )


class MessageTriage(BaseModel):
    intencao: str = Field(..., description=f"One of: {', '.join(MESSAGE_INTENTIONS)}.", examples=["rastreio_pedido"])
    cpf: str | None = Field(default=None, max_length=20, description="Optional CPF used to identify the customer and link the order.", examples=["123.456.789-09"])
    telefone: str | None = Field(default=None, max_length=30, description="Optional phone used to identify the customer and link the order.", examples=["(11) 98877-6655"])
    order_id: str | None = Field(default=None, max_length=40, description="Optional explicit order id when already known.", examples=["PV-000123"])

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"intencao": "rastreio_pedido", "telefone": "(11) 98877-6655"}]
        }
    )


class TicketRespond(BaseModel):
    template_id: str = Field(..., max_length=40, description="Response template chosen for the customer answer.", examples=["TPL-0001"])
    resposta_manual: str | None = Field(default=None, max_length=2000, description="Optional manual note appended after the template.", examples=["Ja acionamos a transportadora e voltamos em ate 2 horas."])

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"template_id": "TPL-0003", "resposta_manual": "Ja acionamos a transportadora e voltamos em ate 2 horas."}
            ]
        }
    )


class MessageResponse(BaseModel):
    message_id: str
    customer_name: str | None = None
    cpf_informado: str | None = None
    telefone_informado: str | None = None
    email_informado: str | None = None
    texto: str
    customer_id: str | None = None
    order_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageInstructorResponse(MessageResponse):
    intencao: str | None = None


class CustomerResponse(BaseModel):
    customer_id: str
    nome: str
    cpf: str | None = None
    telefone: str | None = None
    email: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    valor_total: float
    data_pedido: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipmentResponse(BaseModel):
    shipment_id: str
    order_id: str
    codigo_rastreio: str
    transportadora: str
    status: str
    data_envio: datetime | None = None
    data_entrega_prevista: date | None = None
    data_entrega_real: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketResponse(BaseModel):
    ticket_id: str
    message_id: str
    order_id: str | None = None
    customer_id: str | None = None
    prioridade: str
    sla_horas: int
    resposta_template_id: str | None = None
    status: str
    response_text: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResponseTemplateResponse(BaseModel):
    template_id: str
    intencao: str
    texto: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class Group05StatsResponse(BaseModel):
    messages_by_intencao: dict[str, int]
    tickets_by_prioridade: dict[str, int]
    tickets_by_status: dict[str, int]


class MessageCreateResponse(BaseModel):
    message_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
