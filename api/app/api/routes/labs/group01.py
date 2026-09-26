import json
from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.deps import (
    LABS_GROUP_PATH,
    InstructorKey,
    LabGroupHeader,
    Scenario,
    entity_not_found,
    require_group,
    require_instructor_key,
    scenario_or_422,
)
from ....labs.generators import LAB_TODAY
from ....labs.normalize import duplicate_key_for, normalize_email
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group01_leads import (
    Campaign,
    CampaignResponse,
    DuplicateCheckResponse,
    DuplicateMatch,
    Lead,
    LeadAssign,
    LeadCreate,
    LeadCreateResponse,
    LeadInstructorResponse,
    LeadLabelResponse,
    LeadResponse,
    LeadStatusUpdate,
    Product,
    ProductResponse,
    SalesRep,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 01"
Group01 = Depends(require_group(1))

LEAD_SORT_FIELDS = ("created_at", "updated_at", "status", "nome", "empresa", "origem", "segmento", "regiao")
LABEL_CATEGORIES = (
    "venda_imediata",
    "nurturing",
    "alto_valor",
    "pesquisa_tecnica",
    "reclamacao_comercial",
    "sem_interesse",
    "sem_identificacao",
)

_LEAD_422 = {
    "description": "Simulated validation error requested via ?scenario=validation_error",
    "content": {"application/json": {"example": {"detail": "Simulated validation error"}}},
}


def _lead_or_404(db: Session, lead_id: str) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise entity_not_found("Lead", lead_id)
    return lead


def _duplicates_by_key(db: Session, key: str, limit: int = 20) -> list[Lead]:
    statement = (
        select(Lead)
        .where(Lead.duplicate_key == key)
        .order_by(Lead.created_at.asc(), Lead.lead_id.asc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


def _next_lead_id(db: Session) -> str:
    highest = db.execute(select(Lead.lead_id).order_by(Lead.lead_id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "LEAD-000001"
    return f"LEAD-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _serialize_sales_rep(rep: SalesRep) -> dict:
    return {
        "sales_rep_id": rep.sales_rep_id,
        "nome": rep.nome,
        "email": rep.email,
        "regioes": json.loads(rep.regioes),
        "segmentos": json.loads(rep.segmentos),
        "produtos": json.loads(rep.produtos),
        "active": rep.active,
    }


@router.get(
    f"{PREFIX}/leads",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group01_list_leads",
    summary="List leads with filters, sorting and pagination",
    responses={400: {"description": "Invalid sort field"}, 422: _LEAD_422},
)
async def list_leads(
    scenario: Scenario = None,
    group: LabGroup = Group01,
    status_filter: str | None = Query(default=None, alias="status", description="Filter by lead status."),
    origem: str | None = Query(default=None, description="Filter by acquisition origin."),
    segmento: str | None = Query(default=None),
    regiao: str | None = Query(default=None),
    produto_interesse: str | None = Query(default=None),
    responsavel: str | None = Query(default=None, description="Filter by sales_rep_id owner."),
    search: str | None = Query(default=None, description="Case-insensitive search on nome, empresa, email or mensagem."),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(LEAD_SORT_FIELDS)}."),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Lead)
    if status_filter:
        query = query.where(Lead.status == status_filter)
    if origem:
        query = query.where(Lead.origem == origem)
    if segmento:
        query = query.where(Lead.segmento == segmento)
    if regiao:
        query = query.where(Lead.regiao == regiao)
    if produto_interesse:
        query = query.where(Lead.produto_interesse == produto_interesse)
    if responsavel:
        query = query.where(Lead.responsavel == responsavel)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Lead.nome).like(pattern),
                func.lower(Lead.empresa).like(pattern),
                func.lower(Lead.email).like(pattern),
                func.lower(Lead.mensagem).like(pattern),
            )
        )
    query = apply_sort(query, Lead, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda lead: LeadResponse.model_validate(lead).model_dump())


@router.get(
    f"{PREFIX}/leads/{{lead_id}}",
    response_model=LeadResponse,
    tags=[TAG],
    operation_id="labs_group01_get_lead",
    summary="Get one lead by id",
    responses={404: {"description": "Lead not found"}},
)
async def get_lead(
    lead_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group01,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LeadResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return LeadResponse.model_validate(_lead_or_404(db, lead_id))


@router.post(
    f"{PREFIX}/leads",
    response_model=LeadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group01_create_lead",
    summary="Capture a lead with duplicate detection",
    responses={409: {"description": "Idempotency conflict or duplicate lead"}, 422: _LEAD_422},
)
async def create_lead(
    payload: LeadCreate,
    scenario: Scenario = None,
    group: LabGroup = Group01,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LeadCreateResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group

    key = duplicate_key_for(payload.email, payload.telefone)
    if key and _duplicates_by_key(db, key, limit=1):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate lead detected")

    lead = Lead(
        lead_id=_next_lead_id(db),
        nome=payload.nome,
        empresa=payload.empresa,
        email=payload.email,
        telefone=payload.telefone,
        origem=payload.origem,
        segmento=payload.segmento,
        regiao=payload.regiao,
        produto_interesse=payload.produto_interesse,
        mensagem=payload.mensagem,
        status="NOVO",
        created_at=payload.created_at or datetime.combine(LAB_TODAY, time.min),
        duplicate_key=key,
    )
    lead.updated_at = lead.created_at
    db.add(lead)
    db.commit()
    create_event(
        db,
        event_type="lab_lead_created",
        lab_group=x_lab_group,
        resource_type="lab_lead",
        resource_id=lead.lead_id,
        metadata={"origem": lead.origem, "group": "01"},
    )
    return LeadCreateResponse.model_validate(lead)


@router.post(
    f"{PREFIX}/leads/{{lead_id}}/status",
    response_model=LeadResponse,
    tags=[TAG],
    operation_id="labs_group01_update_lead_status",
    summary="Update lead status and disqualification reason",
    responses={404: {"description": "Lead not found"}, 422: _LEAD_422},
)
async def update_lead_status(
    lead_id: str,
    payload: LeadStatusUpdate,
    scenario: Scenario = None,
    group: LabGroup = Group01,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LeadResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    lead = _lead_or_404(db, lead_id)
    lead.status = payload.status
    if payload.qualificado is not None:
        lead.qualificado = 1 if payload.qualificado else 0
    if payload.motivo_desqualificacao is not None:
        lead.motivo_desqualificacao = payload.motivo_desqualificacao
    if payload.last_contact_at is not None:
        lead.ultimo_contato_em = payload.last_contact_at
    lead.updated_at = datetime.combine(LAB_TODAY, time.min)
    db.commit()
    create_event(
        db,
        event_type="lab_lead_status_changed",
        lab_group=x_lab_group,
        resource_type="lab_lead",
        resource_id=lead.lead_id,
        metadata={"status": lead.status, "group": "01"},
    )
    return LeadResponse.model_validate(lead)


@router.post(
    f"{PREFIX}/leads/{{lead_id}}/assign",
    response_model=LeadResponse,
    tags=[TAG],
    operation_id="labs_group01_assign_lead",
    summary="Assign a lead to a sales rep",
    responses={404: {"description": "Lead or sales rep not found"}, 422: _LEAD_422},
)
async def assign_lead(
    lead_id: str,
    payload: LeadAssign,
    scenario: Scenario = None,
    group: LabGroup = Group01,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LeadResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    lead = _lead_or_404(db, lead_id)
    rep = db.get(SalesRep, payload.responsavel)
    if rep is None:
        raise entity_not_found("SalesRep", payload.responsavel)
    lead.responsavel = rep.sales_rep_id
    lead.updated_at = datetime.combine(LAB_TODAY, time.min)
    db.commit()
    create_event(
        db,
        event_type="lab_lead_assigned",
        lab_group=x_lab_group,
        resource_type="lab_lead",
        resource_id=lead.lead_id,
        metadata={"responsavel": rep.sales_rep_id, "group": "01"},
    )
    return LeadResponse.model_validate(lead)


@router.post(
    f"{PREFIX}/leads/check-duplicates",
    response_model=DuplicateCheckResponse,
    tags=[TAG],
    operation_id="labs_group01_check_duplicates",
    summary="Check whether a lead payload already exists",
    responses={422: _LEAD_422},
)
async def check_duplicates(
    payload: LeadCreate,
    scenario: Scenario = None,
    group: LabGroup = Group01,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> DuplicateCheckResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)

    email_key = normalize_email(payload.email)
    key = email_key or duplicate_key_for(None, payload.telefone)
    if not key:
        return DuplicateCheckResponse(
            duplicate_key="",
            is_duplicate=False,
            match_reason="none",
            matches=[],
        )

    matches = _duplicates_by_key(db, key, limit=20)
    return DuplicateCheckResponse(
        duplicate_key=key,
        is_duplicate=bool(matches),
        match_reason="email" if email_key else "telefone",
        matches=[
            DuplicateMatch(
                lead_id=match.lead_id,
                nome=match.nome,
                empresa=match.empresa,
                status=match.status,
                created_at=match.created_at,
                match_reason="email" if email_key else "telefone",
            )
            for match in matches
        ],
    )


@router.post(
    f"{PREFIX}/instructor/leads/{{lead_id}}/classify",
    response_model=LeadLabelResponse,
    tags=[TAG],
    operation_id="labs_group01_instructor_classify_lead",
    summary="Instructor only: reveal the LLM ground-truth label for a lead",
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled on this environment"},
        404: {"description": "Lead not found"},
        422: {"description": "Lead has no ground truth label"},
    },
)
async def instructor_classify_lead(
    lead_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group01,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LeadLabelResponse:
    require_instructor_key(instructor_key)
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    lead = _lead_or_404(db, lead_id)
    if lead.categoria_sugerida is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lead has no ground truth label. Classify it from the free-text mensagem first.",
        )
    create_event(
        db,
        event_type="lab_lead_classified",
        lab_group=x_lab_group,
        resource_type="lab_lead",
        resource_id=lead.lead_id,
        metadata={"categoria": lead.categoria_sugerida, "group": "01"},
    )
    return LeadLabelResponse(
        lead_id=lead.lead_id,
        categoria_sugerida=lead.categoria_sugerida,
        resumo_llm=lead.resumo_llm or "",
        confianca_llm=lead.confianca_llm or 0.0,
        qualificado=lead.qualificado or 0,
        motivo_desqualificacao=lead.motivo_desqualificacao,
    )


@router.get(
    f"{PREFIX}/instructor/leads/{{lead_id}}",
    response_model=LeadInstructorResponse,
    tags=[TAG],
    operation_id="labs_group01_instructor_get_lead",
    summary="Instructor only: get a lead including its ground-truth label",
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled on this environment"},
        404: {"description": "Lead not found"},
    },
)
async def instructor_get_lead(
    lead_id: str,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group01,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LeadInstructorResponse:
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    return LeadInstructorResponse.model_validate(_lead_or_404(db, lead_id))


@router.get(
    f"{PREFIX}/sales-reps",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group01_list_sales_reps",
    summary="List sales reps available for assignment",
)
async def list_sales_reps(
    scenario: Scenario = None,
    group: LabGroup = Group01,
    include_inactive: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(SalesRep)
    if not include_inactive:
        query = query.where(SalesRep.active.is_(True))
    query = query.order_by(SalesRep.sales_rep_id.asc())
    return build_page(db, query, limit, offset, serializer=_serialize_sales_rep)


@router.get(
    f"{PREFIX}/campaigns",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group01_list_campaigns",
    summary="List acquisition campaigns",
)
async def list_campaigns(
    scenario: Scenario = None,
    group: LabGroup = Group01,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Campaign).order_by(Campaign.campaign_id.asc())
    return build_page(db, query, limit, offset, serializer=lambda item: CampaignResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/products",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group01_list_products",
    summary="List products available for lead interest",
)
async def list_products(
    scenario: Scenario = None,
    group: LabGroup = Group01,
    segmento: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Product)
    if segmento:
        query = query.where(Product.segmento == segmento)
    query = query.order_by(Product.product_id.asc())
    return build_page(db, query, limit, offset, serializer=lambda item: ProductResponse.model_validate(item).model_dump())
