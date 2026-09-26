from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db.database import Base


CANDIDATE_STATUSES = (
    "EM_ANALISE",
    "APROVADO",
    "EM_ONBOARDING",
    "CONCLUIDO",
    "REJEITADO",
)
ACCESS_LEVELS = ("LEITURA", "ESCRITA", "ADMIN")
EQUIPMENT_TYPES = ("NOTEBOOK", "MONITOR", "CELULAR", "HEADSET", "CRACHA")
EQUIPMENT_STATUSES = ("SOLICITADO", "APROVADO", "EMPRESTADO", "DEVOLVIDO")
SECURITY_TYPES = ("BACKGROUND_CHECK", "RG_CPF", "ANTECEDENTES", "ACESSO_PRECIFICADO")
SECURITY_STATUSES = ("PENDENTE", "APROVADO", "REPROVADO", "EXCEPCAO_APROVADA")
DECISOES_ADMISSAO = ("APROVAR", "REJEITAR")


class Candidate(Base):
    __tablename__ = "lab_g09_candidates"

    id_candidato: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    cpf: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cargo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    departamento: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_admissao: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    admissao_excecao: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    admissao_motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    decisao_admissao_esperada: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Onboarding(Base):
    __tablename__ = "lab_g09_onboardings"

    id_onboarding: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    id_candidato: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_fim_prevista: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    responsavel_rh: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AccessMatrix(Base):
    __tablename__ = "lab_g09_access_matrix"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sistema: Mapped[str] = mapped_column(String, nullable=False, index=True)
    perfil: Mapped[str] = mapped_column(String, nullable=False)
    nivel_acesso: Mapped[str] = mapped_column(String, nullable=False, index=True)
    aprovado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    aprovador: Mapped[str | None] = mapped_column(String, nullable=True)
    data_aprovacao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Equipment(Base):
    __tablename__ = "lab_g09_equipment"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    modelo: Mapped[str] = mapped_column(String, nullable=False)
    serial: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    solicitacao_motivo: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SecurityApproval(Base):
    __tablename__ = "lab_g09_security_approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tipo_verificacao: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    verificado_por: Mapped[str | None] = mapped_column(String, nullable=True)
    verificado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parecer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OnboardingTask(Base):
    __tablename__ = "lab_g09_onboarding_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=False, index=True)
    responsavel: Mapped[str] = mapped_column(String, nullable=False)
    prazo: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    concluida: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CandidateCreate(BaseModel):
    nome: str = Field(
        ..., description="Nome do candidato.", examples=["Marina Oliveira"]
    )
    email: str = Field(
        ...,
        description="Email corporativo ou pessoal.",
        examples=["marina.oliveira@example.com"],
    )
    cpf: str = Field(
        ..., description="CPF informado na admissao.", examples=["123.456.789-09"]
    )
    cargo: str = Field(
        ..., description="Cargo de admissao.", examples=["Analista de Dados"]
    )
    departamento: str = Field(
        ..., description="Departamento contratante.", examples=["Tecnologia"]
    )
    data_admissao: date = Field(
        ..., description="Data prevista de admissao.", examples=["2026-09-15"]
    )
    admissao_excecao: bool = Field(
        default=False,
        description="Indica se a admissao depende de excecao.",
        examples=[False],
    )
    admissao_motivo: str | None = Field(
        default=None,
        description="Motivo livre quando ha excecao.",
        examples=["Admissao emergencial aprovada pela diretoria."],
    )
    decisao_admissao_esperada: str = Field(
        ...,
        description="Ground truth do laboratorio para instrutor.",
        examples=["APROVAR"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nome": "Marina Oliveira",
                    "email": "marina.oliveira@example.com",
                    "cpf": "123.456.789-09",
                    "cargo": "Analista de Dados",
                    "departamento": "Tecnologia",
                    "data_admissao": "2026-09-15",
                    "admissao_excecao": True,
                    "admissao_motivo": "Admissao emergencial aprovada pela diretoria.",
                    "decisao_admissao_esperada": "APROVAR",
                }
            ]
        }
    )


class SecurityApprovalCreate(BaseModel):
    tipo_verificacao: str = Field(
        ...,
        description=f"Um de: {', '.join(SECURITY_TYPES)}.",
        examples=["BACKGROUND_CHECK"],
    )
    status: str = Field(
        ...,
        description=f"Um de: {', '.join(SECURITY_STATUSES)}.",
        examples=["APROVADO"],
    )
    verificado_por: str | None = Field(
        default=None,
        description="Responsavel pela verificacao.",
        examples=["analista.seg"],
    )
    parecer: str | None = Field(
        default=None,
        description="Parecer livre da verificacao.",
        examples=["Documentos conferidos sem divergencias."],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tipo_verificacao": "BACKGROUND_CHECK",
                    "status": "APROVADO",
                    "verificado_por": "analista.seg",
                    "parecer": "Documentos conferidos sem divergencias.",
                }
            ]
        }
    )


class EquipmentCreate(BaseModel):
    tipo: str = Field(
        ..., description=f"Um de: {', '.join(EQUIPMENT_TYPES)}.", examples=["NOTEBOOK"]
    )
    modelo: str = Field(
        ..., description="Modelo solicitado.", examples=["QuantumBook Pro 14"]
    )
    serial: str = Field(
        ..., description="Serial deterministico do ativo.", examples=["EQ-2026-0001"]
    )
    solicitacao_motivo: str = Field(
        ...,
        description="Justificativa da solicitacao.",
        examples=["Kit padrao para admissao do time de dados."],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tipo": "NOTEBOOK",
                    "modelo": "QuantumBook Pro 14",
                    "serial": "EQ-2026-0001",
                    "solicitacao_motivo": "Kit padrao para admissao do time de dados.",
                }
            ]
        }
    )


class AccessMatrixCreate(BaseModel):
    sistema: str = Field(..., description="Sistema alvo.", examples=["erp-financeiro"])
    perfil: str = Field(..., description="Perfil funcional.", examples=["analista-rh"])
    nivel_acesso: str = Field(
        ..., description=f"Um de: {', '.join(ACCESS_LEVELS)}.", examples=["LEITURA"]
    )
    aprovado: bool = Field(
        default=True,
        description="Define se o acesso foi aprovado no ato.",
        examples=[True],
    )
    aprovador: str | None = Field(
        default=None, description="Nome do aprovador.", examples=["gestor.ti"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "sistema": "erp-financeiro",
                    "perfil": "analista-rh",
                    "nivel_acesso": "LEITURA",
                    "aprovado": True,
                    "aprovador": "gestor.ti",
                }
            ]
        }
    )


class CandidateResponse(BaseModel):
    id_candidato: str
    nome: str
    email: str
    cpf: str
    cargo: str
    departamento: str
    data_admissao: date
    status: str
    admissao_excecao: bool
    admissao_motivo: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateInstructorResponse(CandidateResponse):
    decisao_admissao_esperada: str


class OnboardingResponse(BaseModel):
    id_onboarding: str
    id_candidato: str
    data_inicio: date
    data_fim_prevista: date
    status: str
    responsavel_rh: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccessMatrixResponse(BaseModel):
    id: str
    candidate_id: str
    sistema: str
    perfil: str
    nivel_acesso: str
    aprovado: bool
    aprovador: str | None = None
    data_aprovacao: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EquipmentResponse(BaseModel):
    id: str
    candidate_id: str
    tipo: str
    modelo: str
    serial: str
    status: str
    solicitacao_motivo: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityApprovalResponse(BaseModel):
    id: str
    candidate_id: str
    tipo_verificacao: str
    status: str
    verificado_por: str | None = None
    verificado_em: datetime | None = None
    parecer: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingTaskResponse(BaseModel):
    id: str
    candidate_id: str
    titulo: str
    categoria: str
    responsavel: str
    prazo: datetime
    concluida: bool
    concluida_em: datetime | None = None
    ordem: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingStatusResponse(BaseModel):
    candidate_id: str
    status_candidato: str
    security_total: int
    security_cleared: int
    equipment_total: int
    equipment_issued: int
    access_total: int
    access_admin_total: int
    tasks_total: int
    tasks_completed: int
    onboarding_status: str | None = None
