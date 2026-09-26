from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


RATE_STATUSES = ("VALIDO", "INVALIDO")
FILE_STATUSES = ("RECEIVED", "PROCESSED", "REJECTED")


class IngestionFile(Base):
    __tablename__ = "lab_g02_ingestion_files"

    file_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome_arquivo: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    origem: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="RECEIVED", index=True
    )
    records_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_invalid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class IndexerMapping(Base):
    __tablename__ = "lab_g02_indexer_mappings"

    mapping_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    indexador: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    codigo: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )


class PrimaryMarketRate(Base):
    __tablename__ = "lab_g02_primary_market_rates"

    rate_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    file_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mes: Mapped[str] = mapped_column(String, nullable=False, index=True)
    indexador: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cnpj: Mapped[str] = mapped_column(String, nullable=False, index=True)
    emissor: Mapped[str] = mapped_column(String, nullable=False, index=True)
    taxa: Mapped[float] = mapped_column(Float, nullable=False)
    vencimento: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="VALIDO", index=True
    )
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class IngestionFileCreate(BaseModel):
    nome_arquivo: str = Field(
        ...,
        min_length=5,
        max_length=180,
        description="Deterministic filename registered for the ingestion batch.",
        examples=["taxas_mercado_primario_2026_09.xlsx"],
    )
    origem: str = Field(
        ...,
        min_length=2,
        max_length=80,
        description="Operational source that delivered the spreadsheet.",
        examples=["tesouraria"],
    )
    status: str = Field(
        default="RECEIVED",
        max_length=20,
        description=(
            f"Lifecycle status for the file. One of: {', '.join(FILE_STATUSES)}."
        ),
        examples=["RECEIVED"],
    )
    created_at: datetime | None = Field(
        default=None,
        description=(
            "Optional deterministic timestamp; defaults to the lab reference instant."
        ),
        examples=["2026-09-13T10:30:00"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nome_arquivo": "taxas_mercado_primario_2026_09.xlsx",
                    "origem": "tesouraria",
                    "status": "RECEIVED",
                }
            ]
        }
    )


class IngestionFileResponse(BaseModel):
    file_id: str
    nome_arquivo: str
    origem: str
    status: str
    records_valid: int
    records_invalid: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IndexerMappingResponse(BaseModel):
    mapping_id: str
    indexador: str
    codigo: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class PrimaryMarketRateResponse(BaseModel):
    rate_id: str
    file_id: str
    line_number: int
    mes: str
    indexador: str
    cnpj: str
    emissor: str
    taxa: float
    vencimento: str
    status: str
    observacao: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
