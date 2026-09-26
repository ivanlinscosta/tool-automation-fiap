import importlib
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings


logger = logging.getLogger(__name__)

LAB_SEED = settings.LABS_SEED
LAB_TODAY = date.fromisoformat(settings.LABS_TODAY)
LAB_MIN_RECORDS = settings.LABS_MIN_RECORDS
LABS_BASE_PATH = "/api/v1/labs"


@dataclass(frozen=True)
class LabGroup:
    group_id: int
    slug: str
    title: str
    tag: str
    models_module: str
    models: tuple[str, ...]
    relations: tuple[tuple[str, str, str], ...]
    probe: str
    summary: str


LAB_GROUPS: dict[int, LabGroup] = {
    1: LabGroup(
        group_id=1,
        slug="prospeccao-leads",
        title="Prospecao e qualificacao de leads",
        tag="Lab - Group 01",
        models_module="app.models.labs.group01_leads",
        models=("Lead", "SalesRep", "Campaign", "Product"),
        relations=(("Lead", "responsavel", "SalesRep.sales_rep_id"),),
        probe="Lead",
        summary="Captura de leads, verificacao de duplicidade, atribuicao de vendedor e qualificacao por LLM.",
    ),
    2: LabGroup(
        group_id=2,
        slug="ingestao-taxas",
        title="Ingestao de taxas do mercado primario",
        tag="Lab - Group 02",
        models_module="app.models.labs.group02_rates",
        models=("PrimaryMarketRate", "IngestionFile", "IndexerMapping"),
        relations=(("PrimaryMarketRate", "file_id", "IngestionFile.file_id"),),
        probe="PrimaryMarketRate",
        summary="Ingestao de planilhas XLSX de taxas, validacao de CNPJ, vencimento e indexador.",
    ),
    3: LabGroup(
        group_id=3,
        slug="revops-bitrix",
        title="RevOps - carga de oportunidades no Bitrix24",
        tag="Lab - Group 03",
        models_module="app.models.labs.group03_bitrix",
        models=(
            "Load",
            "Opportunity",
            "OpportunityValidation",
            "ProductPipelineMap",
            "AuthorizedRequester",
            "CrmUser",
            "CrmContact",
            "CrmDeal",
            "LoadLog",
        ),
        relations=(
            ("Opportunity", "load_id", "Load.carga_id"),
            ("CrmDeal", "contact_id", "CrmContact.contact_id"),
            ("LoadLog", "carga_id", "Load.carga_id"),
        ),
        probe="Opportunity",
        summary="Extracao de lista_free_text para Deals e contatos no Bitrix24 com idempotencia.",
    ),
    4: LabGroup(
        group_id=4,
        slug="atendimento-multicanal",
        title="Atendimento multicanal",
        tag="Lab - Group 04",
        models_module="app.models.labs.group04_support",
        models=("CustomerEvent", "Department"),
        relations=(("CustomerEvent", "departamento", "Department.department_id"),),
        probe="CustomerEvent",
        summary="Triagem de intencao, prioridade, confianca e roteamento por departamento com SLA.",
    ),
    5: LabGroup(
        group_id=5,
        slug="pos-venda-ecommerce",
        title="Atendimento pos-venda e-commerce",
        tag="Lab - Group 05",
        models_module="app.models.labs.group05_pos_venda",
        models=("Message", "Customer", "Order", "Shipment", "Ticket", "ResponseTemplate"),
        relations=(
            ("Order", "customer_id", "Customer.customer_id"),
            ("Shipment", "order_id", "Order.order_id"),
            ("Ticket", "order_id", "Order.order_id"),
            ("Ticket", "customer_id", "Customer.customer_id"),
        ),
        probe="Ticket",
        summary="Classificacao de intencao pos-venda, consulta de pedido por CPF/telefone e SLA.",
    ),
    6: LabGroup(
        group_id=6,
        slug="purchase-order",
        title="Purchase Order",
        tag="Lab - Group 06",
        models_module="app.models.labs.group06_purchase",
        models=("EmailRequest", "PurchaseRequest", "Vendor", "Budget", "PurchaseOrder", "Approval", "Notification"),
        relations=(
            ("PurchaseRequest", "capexNumber", "Budget.capexNumber"),
            ("PurchaseOrder", "capexNumber", "Budget.capexNumber"),
            ("PurchaseOrder", "supplierId", "Vendor.supplierId"),
            ("Approval", "purchaseOrderNumber", "PurchaseOrder.purchaseOrderNumber"),
        ),
        probe="PurchaseOrder",
        summary="Extracao de purchase request por e-mail, checagem de budget e fluxo de aprovacao de PO.",
    ),
    7: LabGroup(
        group_id=7,
        slug="cobranca-financeira",
        title="Cobranca financeira",
        tag="Lab - Group 07",
        models_module="app.models.labs.group07_cobranca",
        models=("Receivable", "CollectionHistory", "CollectionConfig"),
        relations=(("CollectionHistory", "id_titulo", "Receivable.id_titulo"),),
        probe="Receivable",
        summary="Faixas de atraso, decisao de envio, baixa de titulo e reprocessamento idempotente.",
    ),
    8: LabGroup(
        group_id=8,
        slug="desbloqueio-confianca",
        title="Desbloqueio em confianca",
        tag="Lab - Group 08",
        models_module="app.models.labs.group08_unlock",
        models=("UnlockRequest", "CustomerContract", "Invoice", "CreditCheck", "UnlockHistory", "UnlockDecision"),
        relations=(
            ("Invoice", "customer_id", "CustomerContract.customer_id"),
            ("CreditCheck", "customer_id", "CustomerContract.customer_id"),
            ("UnlockHistory", "customer_id", "CustomerContract.customer_id"),
            ("UnlockDecision", "request_id", "UnlockRequest.request_id"),
        ),
        probe="UnlockRequest",
        summary="Decisao de desbloqueio por promessa de pagamento, consulta de credito e provisionamento mock.",
    ),
    9: LabGroup(
        group_id=9,
        slug="onboarding-rh",
        title="Onboarding de RH",
        tag="Lab - Group 09",
        models_module="app.models.labs.group09_onboarding",
        models=("Candidate", "Onboarding", "AccessMatrix", "Equipment", "SecurityApproval", "OnboardingTask"),
        relations=(
            ("Onboarding", "id_candidato", "Candidate.id_candidato"),
            ("SecurityApproval", "candidate_id", "Candidate.id_candidato"),
            ("OnboardingTask", "candidate_id", "Candidate.id_candidato"),
        ),
        probe="Candidate",
        summary="Aprovacao de acessos, solicitacao de equipamentos e excecoes de admissao.",
    ),
    10: LabGroup(
        group_id=10,
        slug="clinica-agendamentos",
        title="Clinica - confirmacao de consultas",
        tag="Lab - Group 10",
        models_module="app.models.labs.group10_clinic",
        models=("Appointment", "PatientMessage", "PatientMessageLabel", "Professional", "Slot", "Waitlist", "WorkflowLog"),
        relations=(
            ("Appointment", "patient_id", "PatientMessage.wa_id"),
            ("Appointment", "professional_id", "Professional.professional_id"),
            ("Slot", "professional_id", "Professional.professional_id"),
            ("Waitlist", "patient_id", "PatientMessage.wa_id"),
            ("WorkflowLog", "appointment_id", "Appointment.appointment_id"),
            ("WorkflowLog", "message_id", "PatientMessage.message_id"),
        ),
        probe="Appointment",
        summary="Confirmacao, cancelamento e remarcacao de consultas por WhatsApp com LLM e human-in-the-loop.",
    ),
    11: LabGroup(
        group_id=11,
        slug="evidencias-restore",
        title="Evidencias de restore",
        tag="Lab - Group 11",
        models_module="app.models.labs.group11_evidences",
        models=("IncomingEmail", "RestoreEvidence", "EvidenceRegistry", "ActionPlan"),
        relations=(
            ("RestoreEvidence", "email_id", "IncomingEmail.email_id"),
            ("EvidenceRegistry", "IC", "RestoreEvidence.IC"),
            ("ActionPlan", "evidence_id", "RestoreEvidence.evidence_id"),
        ),
        probe="RestoreEvidence",
        summary="Analise multimodal de evidencias PDF de restore, divergencias e plano de acao.",
    ),
    12: LabGroup(
        group_id=12,
        slug="handover-modelos-ml",
        title="Handover de modelos de ML",
        tag="Lab - Group 12",
        models_module="app.models.labs.group12_models",
        models=("ModelSubmission", "ModelArtifact", "Metrics", "FeatureSchema", "ModelCard", "ValidationResult", "Deployment", "JiraTicket", "ModelNotification"),
        relations=(
            ("ModelArtifact", "submission_id", "ModelSubmission.submission_id"),
            ("Metrics", "submission_id", "ModelSubmission.submission_id"),
            ("ModelCard", "model_id", "ModelSubmission.modelo_id"),
            ("ValidationResult", "submission_id", "ModelSubmission.submission_id"),
            ("Deployment", "model_id", "ModelSubmission.modelo_id"),
            ("ModelNotification", "submission_id", "ModelSubmission.submission_id"),
        ),
        probe="ModelSubmission",
        summary="Validacao de checksum, schema, documentacao, metricas e compliance antes do deploy de modelos.",
    ),
}

GROUP_TAGS: dict[str, str] = {group.tag: f"{group.group_id:02d}" for group in LAB_GROUPS.values()}


def normalize_group_id(raw: str) -> int | None:
    stripped = raw.strip()
    if stripped.isdigit():
        return int(stripped) if int(stripped) in LAB_GROUPS else None
    if stripped.lower().startswith("group-"):
        suffix = stripped.split("-", maxsplit=1)[1]
        if suffix.isdigit() and int(suffix) in LAB_GROUPS:
            return int(suffix)
    return None


def resolve_group(raw: str) -> LabGroup:
    group_id = normalize_group_id(raw)
    if group_id is None:
        raise KeyError(raw)
    return LAB_GROUPS[group_id]


def load_lab_models(group: LabGroup) -> tuple[type, ...]:
    module = importlib.import_module(group.models_module)
    return tuple(getattr(module, name) for name in group.models)


def group_model_map(group: LabGroup) -> dict[str, type]:
    module = importlib.import_module(group.models_module)
    return {name: getattr(module, name) for name in group.models}


def is_group_seeded(db: Session, group: LabGroup) -> bool:
    model = group_model_map(group)[group.probe]
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def ensure_group_seeded(db: Session, group_id: int) -> None:
    group = LAB_GROUPS[group_id]
    if is_group_seeded(db, group):
        return
    from ..db.labs_seed import load_seeder

    load_seeder(group_id)(db)
    logger.info("Seeded workflow lab group %d (%s)", group_id, group.slug)


def purge_group(db: Session, group_id: int) -> None:
    group = LAB_GROUPS[group_id]
    for model in reversed(load_lab_models(group)):
        db.execute(delete(model))
    db.commit()
    logger.info("Purged lab group %d tables", group_id)
