from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


SUBMISSION_STATUSES = (
    "SUBMETIDO",
    "EM_VALIDACAO",
    "APROVADO",
    "REPROVADO",
    "DEPLOYADO",
)
TARGET_ENVS = ("PROD", "STAGING", "DEV")
DATA_CLASSIFICATIONS = ("PUBLICO", "INTERNO", "CONFIDENCIAL", "RESTRITO")
VALIDATION_STATUSES = ("PASS", "FAIL", "WARNING")
DEPLOYMENT_STATUSES = ("PENDENTE", "EM_ROLLOUT", "CONCLUIDO", "ROLLBACK")
JIRA_STATUSES = ("ABERTO", "EM_ANDAMENTO", "RESOLVIDO")


class ModelSubmission(Base):
    __tablename__ = "lab_g12_model_submissions"

    submission_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    modelo_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    nome_modelo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String, nullable=False, index=True)
    framework: Mapped[str] = mapped_column(String, nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_env: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_classificacao: Mapped[str] = mapped_column(String, nullable=False, index=True)


class ModelArtifact(Base):
    __tablename__ = "lab_g12_model_artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    submission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Metrics(Base):
    __tablename__ = "lab_g12_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    submission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    dataset: Mapped[str] = mapped_column(String, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)


class FeatureSchema(Base):
    __tablename__ = "lab_g12_feature_schema"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    submission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    feature_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    dtype: Mapped[str] = mapped_column(String, nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelCard(Base):
    __tablename__ = "lab_g12_model_cards"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    model_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    intended_use: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    ethical_considerations: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str] = mapped_column(String, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class ValidationResult(Base):
    __tablename__ = "lab_g12_validation_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    submission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    check_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Deployment(Base):
    __tablename__ = "lab_g12_deployments"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    model_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String, nullable=False, index=True)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    replicas: Mapped[int] = mapped_column(Integer, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)


class JiraTicket(Base):
    __tablename__ = "lab_g12_jira_tickets"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    submission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class ModelNotification(Base):
    __tablename__ = "lab_g12_model_notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    submission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    destino: Mapped[str] = mapped_column(String, nullable=False)
    canal: Mapped[str] = mapped_column(String, nullable=False, index=True)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    enviado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    lida: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )


class ModelSubmissionCreate(BaseModel):
    modelo_id: str = Field(
        ...,
        description="Identificador funcional unico do modelo.",
        examples=["mdl-fraud-001"],
    )
    nome_modelo: str = Field(
        ..., description="Nome do modelo.", examples=["Fraud Scorer"]
    )
    version: str = Field(..., description="Versao semantica.", examples=["1.0.0"])
    owner: str = Field(..., description="Owner do modelo.", examples=["time-risco"])
    framework: str = Field(
        ..., description="Framework principal.", examples=["xgboost"]
    )
    target_env: str = Field(
        ..., description=f"Um de: {', '.join(TARGET_ENVS)}.", examples=["PROD"]
    )
    data_classificacao: str = Field(
        ...,
        description=f"Um de: {', '.join(DATA_CLASSIFICATIONS)}.",
        examples=["INTERNO"],
    )
    artifact_size_bytes: int = Field(
        default=512,
        ge=64,
        description="Tamanho do binario do artefato.",
        examples=[512],
    )
    metrics: dict[str, float] = Field(
        ...,
        description="Metricas agregadas do modelo.",
        examples=[
            {"auc": 0.91, "f1": 0.83, "precision": 0.84, "recall": 0.82, "psi": 0.11}
        ],
    )
    feature_schema: list[dict[str, object]] = Field(
        ...,
        description="Schema simplificado das features.",
        examples=[
            [
                {
                    "feature_name": "idade",
                    "dtype": "int",
                    "nullable": False,
                    "min_value": 18,
                    "max_value": 90,
                    "examples": "[25, 41]",
                }
            ]
        ],
    )
    model_card: dict[str, object] = Field(
        ...,
        description="Metadados de model card.",
        examples=[
            {
                "summary": "Modelo de fraude",
                "intended_use": "Priorizar revisao",
                "limitations": "Nao usar isoladamente",
                "ethical_considerations": "Monitorar vies",
                "license": "interna",
                "approved_by": "compliance.ml",
                "completeness": 92,
            }
        ],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "modelo_id": "mdl-fraud-001",
                    "nome_modelo": "Fraud Scorer",
                    "version": "1.0.0",
                    "owner": "time-risco",
                    "framework": "xgboost",
                    "target_env": "PROD",
                    "data_classificacao": "INTERNO",
                    "artifact_size_bytes": 512,
                    "metrics": {
                        "auc": 0.91,
                        "f1": 0.83,
                        "precision": 0.84,
                        "recall": 0.82,
                        "psi": 0.11,
                    },
                    "feature_schema": [
                        {
                            "feature_name": "idade",
                            "dtype": "int",
                            "nullable": False,
                            "min_value": 18,
                            "max_value": 90,
                            "examples": "[25, 41]",
                        },
                        {
                            "feature_name": "renda",
                            "dtype": "float",
                            "nullable": False,
                            "min_value": 0,
                            "max_value": 50000,
                            "examples": "[3200.5, 4500.0]",
                        },
                    ],
                    "model_card": {
                        "summary": "Modelo de fraude para triagem inicial.",
                        "intended_use": "Priorizar revisao humana.",
                        "limitations": "Nao usar como decisao final.",
                        "ethical_considerations": "Monitorar vies por segmento.",
                        "license": "interna",
                        "approved_by": "compliance.ml",
                        "completeness": 92,
                    },
                }
            ]
        }
    )


class ModelSubmissionResponse(BaseModel):
    submission_id: str
    modelo_id: str
    nome_modelo: str
    version: str
    owner: str
    framework: str
    submitted_at: datetime
    status: str
    target_env: str
    data_classificacao: str

    model_config = ConfigDict(from_attributes=True)


class ModelArtifactResponse(BaseModel):
    id: str
    submission_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_path: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetricsResponse(BaseModel):
    id: str
    submission_id: str
    metric_name: str
    metric_value: float
    dataset: str
    evaluated_at: datetime
    threshold: float

    model_config = ConfigDict(from_attributes=True)


class FeatureSchemaResponse(BaseModel):
    id: str
    submission_id: str
    feature_name: str
    dtype: str
    nullable: bool
    min_value: float | None = None
    max_value: float | None = None
    examples: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ModelCardResponse(BaseModel):
    id: str
    model_id: str
    summary: str
    intended_use: str
    limitations: str
    ethical_considerations: str
    license: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    completeness: int

    model_config = ConfigDict(from_attributes=True)


class ValidationResultResponse(BaseModel):
    id: str
    submission_id: str
    check_name: str
    status: str
    detail: str
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentResponse(BaseModel):
    id: str
    model_id: str
    environment: str
    deployed_at: datetime
    status: str
    replicas: int
    endpoint: str

    model_config = ConfigDict(from_attributes=True)


class JiraTicketResponse(BaseModel):
    id: str
    submission_id: str
    key: str
    summary: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelNotificationResponse(BaseModel):
    id: str
    submission_id: str
    destino: str
    canal: str
    mensagem: str
    enviado_em: datetime
    lida: bool

    model_config = ConfigDict(from_attributes=True)


class ValidationSummaryResponse(BaseModel):
    submission_id: str
    overall_status: str
    checks: list[ValidationResultResponse]
