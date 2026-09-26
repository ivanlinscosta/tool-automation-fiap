import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


PURCHASE_REQUEST_STATUSES = ("RECEBIDO", "EM_ANALISE", "APROVADO", "REJEITADO")
PURCHASE_ORDER_STATUSES = ("RASCUNHO", "ENVIADA_APROVACAO", "APROVADA", "REJEITADA", "CONVERTIDA")
APPROVAL_DECISIONS = ("APROVADO", "REJEITADO")
NOTIFICATION_CHANNELS = ("email", "slack")


class EmailRequest(Base):
    __tablename__ = "lab_g06_email_requests"

    request_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    remetente: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assunto: Mapped[str] = mapped_column(String, nullable=False, index=True)
    corpo: Mapped[str] = mapped_column(Text, nullable=False)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    processado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    purchase_request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class Vendor(Base):
    __tablename__ = "lab_g06_vendors"

    supplierId: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cnpj: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    categoria: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    prazo_entrega_dias: Mapped[int] = mapped_column(Integer, nullable=False)


class Budget(Base):
    __tablename__ = "lab_g06_budgets"

    capexNumber: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    centro_custo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    valor_aprovado: Mapped[float] = mapped_column(Float, nullable=False)
    valor_comprometido: Mapped[float] = mapped_column(Float, nullable=False)
    saldo: Mapped[float] = mapped_column(Float, nullable=False)
    vigente_de: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    vigente_ate: Mapped[date] = mapped_column(Date, nullable=False, index=True)


class PurchaseRequest(Base):
    __tablename__ = "lab_g06_purchase_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    email_request_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    capexNumber: Mapped[str] = mapped_column(String, nullable=False, index=True)
    supplierId: Mapped[str] = mapped_column(String, nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    valor_estimado: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class PurchaseOrder(Base):
    __tablename__ = "lab_g06_purchase_orders"

    purchaseOrderNumber: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    request_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    capexNumber: Mapped[str] = mapped_column(String, nullable=False, index=True)
    supplierId: Mapped[str] = mapped_column(String, nullable=False, index=True)
    valor_total: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Approval(Base):
    __tablename__ = "lab_g06_approvals"

    approval_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    purchaseOrderNumber: Mapped[str] = mapped_column(String, nullable=False, index=True)
    aprovador: Mapped[str] = mapped_column(String, nullable=False, index=True)
    decisao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class Notification(Base):
    __tablename__ = "lab_g06_notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    destino: Mapped[str] = mapped_column(String, nullable=False, index=True)
    canal: Mapped[str] = mapped_column(String, nullable=False, index=True)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    enviado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


CAPEX_PATTERN = re.compile(r"CAPEX\s*[:#-]?\s*([A-Z0-9-]+)", re.IGNORECASE)
SUPPLIER_PATTERN = re.compile(r"(?:fornecedor aprovado|fornecedor|supplier)\s*[:#-]?\s*([^.;\n]+)", re.IGNORECASE)
TOTAL_PATTERN = re.compile(r"(?:valor total|montante estimado|total previsto|valor consolidado)\s*[:#-]?\s*R\$\s*([0-9\.,]+)", re.IGNORECASE)
ITEMS_PATTERN = re.compile(r"(?:itens|lista de itens|descricao)\s*[:#-]?\s*([^.;\n]+)", re.IGNORECASE)


def parse_brl_number(raw: str) -> float:
    normalized = raw.strip().replace(".", "").replace(",", ".")
    return round(float(normalized), 2)


def extract_purchase_data(body: str) -> dict[str, str | float] | None:
    capex = CAPEX_PATTERN.search(body)
    supplier = SUPPLIER_PATTERN.search(body)
    total = TOTAL_PATTERN.search(body)
    items = ITEMS_PATTERN.search(body)
    if not capex or not supplier or not total or not items:
        return None
    return {
        "capexNumber": capex.group(1).strip().upper(),
        "supplier_name": supplier.group(1).strip(),
        "valor_estimado": parse_brl_number(total.group(1)),
        "descricao": items.group(1).strip(),
    }


class EmailRequestCreate(BaseModel):
    remetente: str = Field(..., max_length=160, description="Sender e-mail responsible for the purchase request.", examples=["compras@example.com"])
    assunto: str = Field(..., max_length=200, description="E-mail subject line.", examples=["Solicitacao de compra CAPEX CAPEX-0101"])
    corpo: str = Field(..., max_length=4000, description="Free-text e-mail body containing capex, supplier, items and total value.", examples=["Solicito abertura de compra. CAPEX CAPEX-0101. Fornecedor: Alfa Tecnologia. Itens: 5 notebooks. Valor total: R$ 12.500,00."])
    recebido_em: datetime | None = Field(default=None, description="Optional reception timestamp, defaults to the lab reference time.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "remetente": "compras@example.com",
                    "assunto": "Solicitacao de compra CAPEX CAPEX-0101",
                    "corpo": "Solicito abertura de compra. CAPEX CAPEX-0101. Fornecedor: Alfa Tecnologia. Itens: 5 notebooks. Valor total: R$ 12.500,00.",
                }
            ]
        }
    )


class ApprovalDecisionCreate(BaseModel):
    stage: int = Field(..., ge=1, le=3, description="Approval stage. This workflow uses stage 1 then stage 2.", examples=[1])
    aprovador: str = Field(..., max_length=120, description="Approver identifier.", examples=["gerente.compras"])
    comentario: str | None = Field(default=None, max_length=1000, description="Optional approval or rejection note.", examples=["Budget confirmado e fornecedor homologado."])

    model_config = ConfigDict(json_schema_extra={"examples": [{"stage": 1, "aprovador": "gerente.compras", "comentario": "Budget confirmado e fornecedor homologado."}]})


class EmailRequestResponse(BaseModel):
    request_id: str
    remetente: str
    assunto: str
    corpo: str
    recebido_em: datetime
    processado: bool
    purchase_request_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VendorResponse(BaseModel):
    supplierId: str
    nome: str
    cnpj: str | None = None
    categoria: str
    ativo: bool
    prazo_entrega_dias: int

    model_config = ConfigDict(from_attributes=True)


class BudgetResponse(BaseModel):
    capexNumber: str
    centro_custo: str
    valor_aprovado: float
    valor_comprometido: float
    saldo: float
    vigente_de: date
    vigente_ate: date

    model_config = ConfigDict(from_attributes=True)


class PurchaseRequestResponse(BaseModel):
    id: str
    email_request_id: str
    capexNumber: str
    supplierId: str
    descricao: str
    valor_estimado: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderResponse(BaseModel):
    purchaseOrderNumber: str
    request_id: str
    capexNumber: str
    supplierId: str
    valor_total: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalResponse(BaseModel):
    approval_id: str
    purchaseOrderNumber: str
    aprovador: str
    decisao: str
    comentario: str | None = None
    decided_at: datetime
    stage: int

    model_config = ConfigDict(from_attributes=True)


class NotificationResponse(BaseModel):
    id: str
    destino: str
    canal: str
    mensagem: str
    enviado_em: datetime
    lida: bool

    model_config = ConfigDict(from_attributes=True)


class BudgetCheckResponse(BaseModel):
    purchase_request_id: str
    capexNumber: str
    valor_estimado: float
    saldo: float
    approved: bool
    missing_amount: float


class PurchaseOrderStatusResponse(BaseModel):
    purchase_order: PurchaseOrderResponse
    approvals: list[ApprovalResponse]
    next_stage: int | None = None
    fully_approved: bool
