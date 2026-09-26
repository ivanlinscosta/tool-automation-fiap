import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.deps import (
    InstructorKey,
    LABS_GROUP_PATH,
    LabGroupHeader,
    Scenario,
    entity_not_found,
    require_group,
    require_instructor_key,
    scenario_or_422,
)
from ....labs.generators import CHANNELS, LAB_NOW
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group04_support import (
    Department,
    DepartmentResponse,
    LEVELS,
    CustomerEvent,
    CustomerEventCreate,
    CustomerEventInstructorResponse,
    CustomerEventResolve,
    CustomerEventResponse,
    CustomerEventRoute,
    CustomerEventStatsRow,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 04"
Group04 = Depends(require_group(4))
EVENT_SORT_FIELDS = (
    "event_id",
    "customer_id",
    "canal",
    "prioridade",
    "sla_horas",
    "status",
    "created_at",
    "resolved_at",
)
DEPARTMENT_SORT_FIELDS = ("department_id", "nome", "sla_horas_padrao", "ativo")

_GROUP04_422 = {
    "description": (
        "Simulated validation error requested via ?scenario=validation_error"
    ),
    "content": {
        "application/json": {"example": {"detail": "Simulated validation error"}}
    },
}

INTENT_DEPARTMENT = {
    "cancelamento": "DEP-01",
    "troca": "DEP-02",
    "duvida_produto": "DEP-03",
    "reclamacao": "DEP-04",
    "elogio": "DEP-05",
    "reclamacao_financ": "DEP-06",
    "upgrade": "DEP-07",
}


def _event_or_404(db: Session, event_id: str) -> CustomerEvent:
    event = db.get(CustomerEvent, event_id)
    if event is None:
        raise entity_not_found("CustomerEvent", event_id)
    return event


def _department_or_404(db: Session, department_id: str) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise entity_not_found("Department", department_id)
    return department


def _next_event_id(db: Session) -> str:
    highest = db.execute(
        select(CustomerEvent.event_id).order_by(CustomerEvent.event_id.desc()).limit(1)
    ).scalar_one_or_none()
    if highest is None:
        return "EVT-000001"
    return f"EVT-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _classify_intent(message: str) -> str:
    cleaned = message.lower()
    if "cancel" in cleaned or "encerrar" in cleaned:
        return "cancelamento"
    if "troc" in cleaned or "substit" in cleaned:
        return "troca"
    if "duvida" in cleaned or "integracao" in cleaned or "diferenca" in cleaned:
        return "duvida_produto"
    if "elogio" in cleaned or "parabens" in cleaned or "agrade" in cleaned:
        return "elogio"
    if (
        "fatura" in cleaned
        or "cobranc" in cleaned
        or "desconto" in cleaned
        or "valor indevido" in cleaned
    ):
        return "reclamacao_financ"
    if "upgrade" in cleaned or "ampli" in cleaned or "aumentar" in cleaned:
        return "upgrade"
    return "reclamacao"


def _priority(intent: str, impacto: str, urgencia: str) -> tuple[str, int]:
    if intent in {"cancelamento", "reclamacao_financ"} and "alto" in {
        impacto,
        urgencia,
    }:
        return "P1", 4
    if impacto == "alto" and urgencia == "alto":
        return "P1", 4
    if impacto == "alto" or urgencia == "alto":
        return "P2", 8
    if impacto == "medio" or urgencia == "medio":
        return "P3", 16
    return "P4", 24


def _confidence(intent: str, message: str) -> float:
    digest = hashlib.sha1(f"{intent}:{message}".encode("utf-8")).hexdigest()
    bucket = int(digest[:4], 16) / 0xFFFF
    return round(0.6 + bucket * 0.39, 4)


@router.get(
    f"{PREFIX}/customer-events",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group04_list_customer_events",
    summary="List customer events without exposing instructor-only intent labels",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP04_422},
)
async def list_customer_events(
    scenario: Scenario = None,
    group: LabGroup = Group04,
    canal: str | None = Query(default=None, description="Filter by intake channel."),
    intencao: str | None = Query(
        default=None,
        description="Optional hidden-label filter for instructor-authored exercises.",
    ),
    prioridade: str | None = Query(
        default=None, description="Filter by computed priority."
    ),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by event status."
    ),
    departamento: str | None = Query(
        default=None, description="Filter by assigned department id."
    ),
    has_department: bool | None = Query(
        default=None,
        description=(
            "When true returns only routed events; when false returns unrouted ones."
        ),
    ),
    search: str | None = Query(
        default=None, description="Case-insensitive search on customer_id or mensagem."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(EVENT_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(CustomerEvent)
    if canal:
        query = query.where(CustomerEvent.canal == canal)
    if intencao:
        query = query.where(CustomerEvent.intencao == intencao)
    if prioridade:
        query = query.where(CustomerEvent.prioridade == prioridade)
    if status_filter:
        query = query.where(CustomerEvent.status == status_filter)
    if departamento:
        query = query.where(CustomerEvent.departamento == departamento)
    if has_department is True:
        query = query.where(CustomerEvent.departamento.is_not(None))
    if has_department is False:
        query = query.where(CustomerEvent.departamento.is_(None))
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(CustomerEvent.customer_id).like(pattern),
                func.lower(CustomerEvent.mensagem).like(pattern),
            )
        )
    query = (
        apply_sort(query, CustomerEvent, sort, order)
        if sort
        else query.order_by(CustomerEvent.event_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: CustomerEventResponse.model_validate(item).model_dump(),
    )


@router.get(
    f"{PREFIX}/customer-events/stats",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group04_customer_event_stats",
    summary="Aggregate customer event counts by channel, intent and priority",
    responses={422: _GROUP04_422},
)
async def customer_event_stats(
    scenario: Scenario = None,
    group: LabGroup = Group04,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    rows = db.execute(
        select(
            CustomerEvent.canal,
            CustomerEvent.intencao,
            CustomerEvent.prioridade,
            func.count().label("total"),
        )
        .group_by(CustomerEvent.canal, CustomerEvent.intencao, CustomerEvent.prioridade)
        .order_by(
            CustomerEvent.canal.asc(),
            CustomerEvent.intencao.asc(),
            CustomerEvent.prioridade.asc(),
        )
    ).all()
    items = [
        CustomerEventStatsRow(
            canal=canal, intencao=intencao, prioridade=prioridade, total=total
        ).model_dump()
        for canal, intencao, prioridade, total in rows
    ]
    return {"items": items, "meta": {"total": len(items)}}


@router.post(
    f"{PREFIX}/customer-events",
    response_model=CustomerEventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group04_create_customer_event",
    summary="Register a new multi-channel customer event intake",
    responses={422: _GROUP04_422},
)
async def create_customer_event(
    payload: CustomerEventCreate,
    scenario: Scenario = None,
    group: LabGroup = Group04,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CustomerEventResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if payload.canal not in CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown channel '{payload.canal}'",
        )
    if payload.impacto not in LEVELS or payload.urgencia not in LEVELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Impacto e urgencia devem ser alto, medio ou baixo",
        )
    intent = _classify_intent(payload.mensagem)
    prioridade, sla_horas = _priority(intent, payload.impacto, payload.urgencia)
    created_at = min(payload.created_at or LAB_NOW, LAB_NOW)
    event = CustomerEvent(
        event_id=_next_event_id(db),
        customer_id=payload.customer_id,
        canal=payload.canal,
        mensagem=payload.mensagem,
        intencao=intent,
        prioridade=prioridade,
        confianca=_confidence(intent, payload.mensagem),
        sla_horas=sla_horas,
        departamento=None,
        impacto=payload.impacto,
        urgencia=payload.urgencia,
        created_at=created_at,
        resolved_at=None,
        status="novo",
    )
    db.add(event)
    db.commit()
    create_event(
        db,
        event_type="lab_group04_event_created",
        lab_group=x_lab_group,
        resource_type="lab_customer_event",
        resource_id=event.event_id,
        metadata={"group": "04", "canal": event.canal, "prioridade": event.prioridade},
    )
    return CustomerEventResponse.model_validate(event)


@router.post(
    f"{PREFIX}/customer-events/{{event_id}}/route",
    response_model=CustomerEventResponse,
    tags=[TAG],
    operation_id="labs_group04_route_customer_event",
    summary="Assign a customer event to an active department",
    responses={
        404: {"description": "Event or department not found"},
        422: _GROUP04_422,
    },
)
async def route_customer_event(
    event_id: str,
    payload: CustomerEventRoute,
    scenario: Scenario = None,
    group: LabGroup = Group04,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CustomerEventResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    event = _event_or_404(db, event_id)
    department = _department_or_404(db, payload.departamento)
    if not department.ativo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Department is inactive",
        )
    event.departamento = department.department_id
    event.status = "roteado"
    db.commit()
    create_event(
        db,
        event_type="lab_group04_event_routed",
        lab_group=x_lab_group,
        resource_type="lab_customer_event",
        resource_id=event.event_id,
        metadata={"group": "04", "departamento": department.department_id},
    )
    return CustomerEventResponse.model_validate(event)


@router.post(
    f"{PREFIX}/customer-events/{{event_id}}/resolve",
    response_model=CustomerEventResponse,
    tags=[TAG],
    operation_id="labs_group04_resolve_customer_event",
    summary="Resolve a customer event and stamp its deterministic resolution time",
    responses={404: {"description": "Event not found"}, 422: _GROUP04_422},
)
async def resolve_customer_event(
    event_id: str,
    payload: CustomerEventResolve,
    scenario: Scenario = None,
    group: LabGroup = Group04,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CustomerEventResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    event = _event_or_404(db, event_id)
    event.status = payload.status
    resolved_at = payload.resolved_at or LAB_NOW
    event.resolved_at = (
        resolved_at if resolved_at >= event.created_at else event.created_at
    )
    db.commit()
    create_event(
        db,
        event_type="lab_group04_event_resolved",
        lab_group=x_lab_group,
        resource_type="lab_customer_event",
        resource_id=event.event_id,
        metadata={"group": "04", "status": event.status},
    )
    return CustomerEventResponse.model_validate(event)


@router.get(
    f"{PREFIX}/customer-events/{{event_id}}",
    response_model=CustomerEventResponse,
    tags=[TAG],
    operation_id="labs_group04_get_customer_event",
    summary="Get one customer event without exposing instructor-only labels",
    responses={404: {"description": "Event not found"}, 422: _GROUP04_422},
)
async def get_customer_event(
    event_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group04,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CustomerEventResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return CustomerEventResponse.model_validate(_event_or_404(db, event_id))


@router.get(
    f"{PREFIX}/departments",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group04_list_departments",
    summary="List departments available for event routing",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP04_422},
)
async def list_departments(
    scenario: Scenario = None,
    group: LabGroup = Group04,
    active_only: bool = Query(
        default=False, description="Return only active departments when true."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(DEPARTMENT_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Department)
    if active_only:
        query = query.where(Department.ativo.is_(True))
    query = (
        apply_sort(query, Department, sort, order)
        if sort
        else query.order_by(Department.department_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: DepartmentResponse.model_validate(item).model_dump(),
    )


@router.get(
    f"{PREFIX}/instructor/customer-events/{{event_id}}",
    response_model=CustomerEventInstructorResponse,
    tags=[TAG],
    operation_id="labs_group04_instructor_get_customer_event",
    summary=(
        "Instructor only: reveal the hidden intent and confidence for one "
        "customer event"
    ),
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled on this environment"},
        404: {"description": "Event not found"},
        422: _GROUP04_422,
    },
)
async def instructor_get_customer_event(
    event_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group04,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CustomerEventInstructorResponse:
    await apply_scenario(scenario_or_422(scenario))
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    return CustomerEventInstructorResponse.model_validate(_event_or_404(db, event_id))
