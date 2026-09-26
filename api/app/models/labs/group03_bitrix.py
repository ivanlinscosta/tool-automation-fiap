from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


OPPORTUNITY_STAGES = ("novo", "qualificado", "proposta", "ganho", "perdido")
LOAD_STATUSES = ("PROCESSADO", "PARCIAL", "REJEITADO")
LOG_LEVELS = ("INFO", "WARN", "ERROR")


class Load(Base):
    __tablename__ = "lab_g03_loads"

    carga_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    requester_email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    lista_free_text: Mapped[str] = mapped_column(Text, nullable=False)
    chave_idempotencia: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    payload_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="PROCESSADO", index=True
    )
    opportunities_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deals_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Opportunity(Base):
    __tablename__ = "lab_g03_opportunities"

    opportunity_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    load_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    empresa: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cnpj: Mapped[str] = mapped_column(String, nullable=False, index=True)
    produto: Mapped[str] = mapped_column(String, nullable=False, index=True)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    contato_nome: Mapped[str] = mapped_column(String, nullable=False)
    contato_email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stage: Mapped[str] = mapped_column(
        String, nullable=False, default="novo", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class OpportunityValidation(Base):
    __tablename__ = "lab_g03_opportunity_validations"

    validation_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    opportunity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cnpj_valido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valor_valido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    produto_mapeado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class ProductPipelineMap(Base):
    __tablename__ = "lab_g03_product_pipeline_maps"

    map_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    produto: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    pipeline_codigo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    etapa_padrao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )


class AuthorizedRequester(Base):
    __tablename__ = "lab_g03_authorized_requesters"

    requester_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    area: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )


class CrmUser(Base):
    __tablename__ = "lab_g03_crm_users"

    crm_user_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )


class CrmContact(Base):
    __tablename__ = "lab_g03_crm_contacts"

    contact_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    empresa: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cnpj: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class CrmDeal(Base):
    __tablename__ = "lab_g03_crm_deals"

    deal_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    contact_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    opportunity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    load_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    pipeline_codigo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String, nullable=False, index=True)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    bitrix_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class LoadLog(Base):
    __tablename__ = "lab_g03_load_logs"

    log_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    carga_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    level: Mapped[str] = mapped_column(
        String, nullable=False, default="INFO", index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class LoadCreate(BaseModel):
    requester_email: str = Field(
        ...,
        max_length=160,
        description=(
            "Email of the RevOps requester. Only active authorized requesters "
            "can create loads."
        ),
        examples=["revops.01@example.com"],
    )
    lista_free_text: str = Field(
        ...,
        min_length=10,
        max_length=20000,
        description=(
            "Free-text list with one opportunity per line using the pattern "
            "empresa | cnpj | produto | valor | contato | email | stage."
        ),
        examples=[
            "Estrela Logistica | 12.345.678/0001-95 | CRM Enterprise | "
            "145000.0 | Helena Braga | helena.braga@example.com | proposta"
        ],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "requester_email": "revops.01@example.com",
                    "lista_free_text": (
                        "Estrela Logistica | 12.345.678/0001-95 | CRM Enterprise | "
                        "145000.0 | Helena Braga | helena.braga@example.com | "
                        "proposta\n"
                        "Boreal Energia | 98.765.432/0001-87 | Analytics Pro | "
                        "92000.0 | Bruno Souza | bruno.souza@example.com | qualificado"
                    ),
                }
            ]
        }
    )


class OpportunityValidateRequest(BaseModel):
    requested_by: str = Field(
        default="manual-review",
        max_length=80,
        description="Actor requesting a new validation pass for the opportunity.",
        examples=["manual-review"],
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"requested_by": "manual-review"}]}
    )


class LoadResponse(BaseModel):
    carga_id: str
    requester_email: str
    lista_free_text: str
    chave_idempotencia: str | None = None
    status: str
    opportunities_count: int
    deals_created: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityResponse(BaseModel):
    opportunity_id: str
    load_id: str
    line_number: int
    empresa: str
    cnpj: str
    produto: str
    valor: float
    contato_nome: str
    contato_email: str
    stage: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityValidationResponse(BaseModel):
    validation_id: str
    opportunity_id: str
    cnpj_valido: bool
    valor_valido: bool
    produto_mapeado: bool
    motivo: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductPipelineMapResponse(BaseModel):
    map_id: str
    produto: str
    pipeline_codigo: str
    etapa_padrao: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class AuthorizedRequesterResponse(BaseModel):
    requester_id: str
    nome: str
    email: str
    area: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class CrmUserResponse(BaseModel):
    crm_user_id: str
    nome: str
    email: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class CrmContactResponse(BaseModel):
    contact_id: str
    nome: str
    email: str
    empresa: str
    cnpj: str
    owner_user_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CrmDealResponse(BaseModel):
    deal_id: str
    contact_id: str
    opportunity_id: str
    load_id: str
    pipeline_codigo: str
    stage: str
    valor: float
    bitrix_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoadLogResponse(BaseModel):
    log_id: str
    carga_id: str
    level: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoadSyncResponse(BaseModel):
    carga_id: str
    status: str
    deals_created: int
    deals: list[CrmDealResponse]


class LoadCreateRejected(BaseModel):
    message: str
    carga_id: str
