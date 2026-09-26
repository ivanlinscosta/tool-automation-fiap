from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


LEAD_STATUSES = (
    "NOVO",
    "EM_QUALIFICACAO",
    "QUALIFICADO",
    "DESQUALIFICADO",
    "CONVERTIDO",
    "DESCARTADO",
)

LEAD_ORIGINS = (
    "site",
    "indicacao",
    "linkedin",
    "evento",
    "email_marketing",
    "outbound",
    "whatsapp",
    "parceiro",
)

LEAD_SUGGESTED_CATEGORIES = (
    "venda_imediata",
    "nurturing",
    "alto_valor",
    "pesquisa_tecnica",
    "reclamacao_comercial",
    "sem_interesse",
    "sem_identificacao",
)


class SalesRep(Base):
    __tablename__ = "lab_g01_sales_reps"

    sales_rep_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    regioes: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    segmentos: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    produtos: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class Campaign(Base):
    __tablename__ = "lab_g01_campaigns"

    campaign_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    origem: Mapped[str] = mapped_column(String, nullable=False, index=True)
    produto: Mapped[str] = mapped_column(String, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class Product(Base):
    __tablename__ = "lab_g01_products"

    product_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    segmento: Mapped[str] = mapped_column(String, nullable=False, index=True)


class Lead(Base):
    __tablename__ = "lab_g01_leads"

    lead_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str | None] = mapped_column(String, nullable=True)
    empresa: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    telefone: Mapped[str | None] = mapped_column(String, nullable=True)
    origem: Mapped[str] = mapped_column(String, nullable=False, index=True)
    segmento: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    regiao: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    produto_interesse: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="NOVO", index=True)
    responsavel: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ultimo_contato_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    categoria_sugerida: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    resumo_llm: Mapped[str | None] = mapped_column(Text, nullable=True)
    confianca_llm: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualificado: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    motivo_desqualificacao: Mapped[str | None] = mapped_column(String, nullable=True)
    duplicate_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class LeadCreate(BaseModel):
    nome: str | None = Field(default=None, max_length=160, description="Full name of the lead, optional when the message is anonymous.")
    empresa: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=160)
    telefone: str | None = Field(default=None, max_length=40)
    origem: str = Field(..., max_length=60, description=f"One of: {', '.join(LEAD_ORIGINS)}.")
    segmento: str | None = Field(default=None, max_length=60)
    regiao: str | None = Field(default=None, max_length=60)
    produto_interesse: str | None = Field(default=None, max_length=120)
    mensagem: str | None = Field(default=None, max_length=4000, description="Free text message written by the lead.")
    created_at: datetime | None = Field(default=None, description="Optional event timestamp, defaults to the lab reference date.")
    idempotency_key: str | None = Field(default=None, max_length=120, description="Optional client key; the same key never creates two leads.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nome": "Helena Braga",
                    "empresa": "Estrela Logistica",
                    "email": "helena.braga@example.com",
                    "telefone": "(11) 98877-1200",
                    "origem": "site",
                    "segmento": "mid_market",
                    "regiao": "Sudeste",
                    "produto_interesse": "Quantum Analytics",
                    "mensagem": "Precisamos de um orcamento para 40 licences do Quantum Analytics ate o fim do mes.",
                }
            ]
        }
    )


class LeadStatusUpdate(BaseModel):
    status: str = Field(..., description=f"One of: {', '.join(LEAD_STATUSES)}.")
    motivo_desqualificacao: str | None = Field(default=None, max_length=300)
    qualificado: bool | None = Field(default=None, description="Optional boolean flag mirroring the status decision.")
    last_contact_at: datetime | None = Field(default=None, description="Sets ultimo_contato_em when provided.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "QUALIFICADO", "qualificado": True},
                {"status": "DESQUALIFICADO", "motivo_desqualificacao": "Semorcamento aprovado no trimestre"},
            ]
        }
    )


class LeadAssign(BaseModel):
    responsavel: str = Field(..., min_length=1, max_length=60, description="sales_rep_id of the rep that will own the lead.")

    model_config = ConfigDict(json_schema_extra={"examples": [{"responsavel": "SR-01"}]})


class LeadCreateResponse(BaseModel):
    lead_id: str
    status: str
    duplicate_key: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadResponse(BaseModel):
    lead_id: str
    nome: str | None = None
    empresa: str | None = None
    email: str | None = None
    telefone: str | None = None
    origem: str
    segmento: str | None = None
    regiao: str | None = None
    produto_interesse: str | None = None
    mensagem: str | None = None
    status: str
    responsavel: str | None = None
    created_at: datetime
    updated_at: datetime
    ultimo_contato_em: datetime | None = None
    qualificado: int | None = None
    motivo_desqualificacao: str | None = None
    duplicate_key: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LeadInstructorResponse(LeadResponse):
    categoria_sugerida: str | None = None
    resumo_llm: str | None = None
    confianca_llm: float | None = None


class SalesRepResponse(BaseModel):
    sales_rep_id: str
    nome: str
    email: str
    regioes: list[str]
    segmentos: list[str]
    produtos: list[str]
    active: bool


class CampaignResponse(BaseModel):
    campaign_id: str
    nome: str
    origem: str
    produto: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    product_id: str
    nome: str
    segmento: str

    model_config = ConfigDict(from_attributes=True)


class DuplicateMatch(BaseModel):
    lead_id: str
    nome: str | None = None
    empresa: str | None = None
    status: str
    created_at: datetime
    match_reason: str = Field(description="Which normalized field produced the match: email, telefone, empresa or nome+empresa.")

    model_config = ConfigDict(from_attributes=True)


class DuplicateCheckResponse(BaseModel):
    duplicate_key: str
    is_duplicate: bool
    match_reason: str
    matches: list[DuplicateMatch] = Field(default_factory=list)


class LeadLabelResponse(BaseModel):
    lead_id: str
    categoria_sugerida: str
    resumo_llm: str
    confianca_llm: float
    qualificado: int
    motivo_desqualificacao: str | None = None
