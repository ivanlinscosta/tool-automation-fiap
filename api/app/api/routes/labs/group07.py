from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
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
from ....labs.generators import LAB_NOW
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group07_cobranca import (
    BulkSendRequest,
    BulkSendResult,
    CollectionConfig,
    CollectionConfigResponse,
    CollectionDecisionResponse,
    CollectionHistory,
    CollectionHistoryResponse,
    Receivable,
    ReceivableInstructorResponse,
    ReceivableResponse,
    WriteOffRequest,
    faixa_label,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 07"
Group07 = Depends(require_group(7))

RECEIVABLE_SORT_FIELDS = ("data_vencimento", "dias_atraso", "valor", "status", "updated_at")
CONFIG_SORT_FIELDS = ("ordem", "faixa_inicio", "acao")
HISTORY_SORT_FIELDS = ("enviada_em", "resultado", "acao")

_RESPONSES_422 = {
    "description": "Simulated validation error requested via ?scenario=validation_error",
    "content": {"application/json": {"example": {"detail": "Simulated validation error"}}},
}


def _receivable_or_404(db: Session, receivable_id: str) -> Receivable:
    receivable = db.get(Receivable, receivable_id)
    if receivable is None:
        raise entity_not_found("Receivable", receivable_id)
    return receivable


def _next_history_id(db: Session) -> str:
    highest = db.execute(select(CollectionHistory.id).order_by(CollectionHistory.id.desc()).limit(1)).scalar_one_or_none()
    pending = sum(1 for item in db.new if isinstance(item, CollectionHistory))
    base = int(highest.rsplit('-', maxsplit=1)[1]) if highest is not None else 0
    return f"HIS-{base + pending + 1:06d}"


def _applicable_config(db: Session, receivable: Receivable) -> CollectionConfig | None:
    if not receivable.deve_enviar or receivable.status != "VENCIDO":
        return None
    configs = db.execute(select(CollectionConfig).where(CollectionConfig.ativo.is_(True)).order_by(CollectionConfig.ordem.asc())).scalars().all()
    for config in configs:
        upper = config.faixa_fim if config.faixa_fim is not None else 100_000
        if config.faixa_inicio <= receivable.dias_atraso <= upper:
            return config
    return None


def _history_for_receivable(db: Session, receivable_id: str) -> list[CollectionHistory]:
    query = select(CollectionHistory).where(CollectionHistory.id_titulo == receivable_id).order_by(CollectionHistory.enviada_em.asc(), CollectionHistory.id.asc())
    return list(db.execute(query).scalars().all())


def _send_history(db: Session, receivable: Receivable, config: CollectionConfig | None) -> CollectionHistory:
    same_day = LAB_NOW.date()
    existing = None
    for item in _history_for_receivable(db, receivable.id_titulo):
        if item.enviada_em.date() != same_day:
            continue
        if config is None and item.config_id is None and item.acao == "IGNORADO":
            existing = item
            break
        if config is not None and item.config_id == config.config_id:
            existing = item
            break
    if existing is not None:
        return existing

    if config is None:
        history = CollectionHistory(
            id=_next_history_id(db),
            id_titulo=receivable.id_titulo,
            config_id=None,
            acao="IGNORADO",
            canal="workflow",
            mensagem_enviada="Nenhuma acao de cobranca aplicavel para este titulo.",
            enviada_em=LAB_NOW,
            resultado="IGNORADO",
            respondedido=True,
            motivo="fora_da_regra",
        )
        db.add(history)
        return history

    resultado = "SUCESSO"
    motivo = None
    if config.canal in {"sms", "phone"} and not receivable.customer_phone:
        resultado = "FALHA"
        motivo = "cliente nao possui telefone"
    elif config.canal == "phone" and int(receivable.id_titulo.rsplit('-', maxsplit=1)[1]) % 7 == 0:
        resultado = "FALHA"
        motivo = "canal indisponivel"
    history = CollectionHistory(
        id=_next_history_id(db),
        id_titulo=receivable.id_titulo,
        config_id=config.config_id,
        acao=config.acao,
        canal=config.canal,
        mensagem_enviada=f"{config.template_mensagem} Titulo {receivable.id_titulo} valor R$ {receivable.valor:.2f}.",
        enviada_em=LAB_NOW,
        resultado=resultado,
        respondedido=resultado != "FALHA",
        motivo=motivo,
    )
    db.add(history)
    return history


@router.get(
    f"{PREFIX}/receivables",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group07_list_receivables",
    summary="List receivables with status, aging and customer filters",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_receivables(
    scenario: Scenario = None,
    group: LabGroup = Group07,
    status_filter: str | None = Query(default=None, alias="status"),
    faixa: str | None = Query(default=None),
    customer: str | None = Query(default=None),
    overdue_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(RECEIVABLE_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Receivable)
    if status_filter:
        query = query.where(Receivable.status == status_filter)
    if customer:
        pattern = f"%{customer.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Receivable.customer_id).like(pattern),
                func.lower(Receivable.customer_name).like(pattern),
            )
        )
    if overdue_only:
        query = query.where(Receivable.dias_atraso > 0)
    if faixa:
        candidates = [item.id_titulo for item in db.execute(select(Receivable)).scalars().all() if faixa_label(item.dias_atraso) == faixa]
        query = query.where(Receivable.id_titulo.in_(candidates)) if candidates else query.where(Receivable.id_titulo == "__none__")
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Receivable.id_titulo).like(pattern),
                func.lower(Receivable.customer_name).like(pattern),
                func.lower(func.coalesce(Receivable.customer_document, "")).like(pattern),
            )
        )
    query = apply_sort(query, Receivable, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: ReceivableResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/configs",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group07_list_configs",
    summary="List collection configuration rules",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_configs(
    scenario: Scenario = None,
    group: LabGroup = Group07,
    ativo: bool | None = Query(default=None),
    acao: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(CONFIG_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(CollectionConfig)
    if ativo is not None:
        query = query.where(CollectionConfig.ativo.is_(ativo))
    if acao:
        query = query.where(CollectionConfig.acao == acao)
    query = apply_sort(query, CollectionConfig, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: CollectionConfigResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/history",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group07_list_history",
    summary="List collection history events",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_history(
    group_id: str,
    scenario: Scenario = None,
    receivable_id: str | None = Query(default=None, alias="id_titulo"),
    resultado: str | None = Query(default=None),
    request_id: str | None = Query(default=None, description="Group 08 filter by unlock request id."),
    acao: str | None = Query(default=None, description="Group 08 filter by workflow action."),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(HISTORY_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    from ....api.routes.labs import group08 as group08_module
    from ....labs.deps import lab_group

    resolved = lab_group(group_id, db)
    if resolved.group_id == 8:
        return await group08_module.list_history(
            scenario=None,
            group=resolved,
            request_id=request_id or receivable_id,
            acao=acao or resultado,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
            x_lab_group=x_lab_group,
            db=db,
        )
    if resolved.group_id != 7:
        raise HTTPException(status_code=404, detail="Endpoint does not belong to lab group 07 or 08")

    _ = x_lab_group
    query = select(CollectionHistory)
    if receivable_id:
        query = query.where(CollectionHistory.id_titulo == receivable_id)
    if resultado:
        query = query.where(CollectionHistory.resultado == resultado)
    query = apply_sort(query, CollectionHistory, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: CollectionHistoryResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/receivables/aging",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group07_receivables_aging",
    summary="Compute the aging report in SQL buckets",
    responses={422: _RESPONSES_422},
)
async def receivables_aging(
    scenario: Scenario = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    faixa_case = case(
        (Receivable.dias_atraso <= 0, "em_dia"),
        (Receivable.dias_atraso <= 15, "1-15"),
        (Receivable.dias_atraso <= 30, "16-30"),
        (Receivable.dias_atraso <= 60, "31-60"),
        (Receivable.dias_atraso <= 90, "61-90"),
        else_="90+",
    )
    rows = db.execute(
        select(faixa_case.label("faixa"), func.count().label("quantidade"), func.round(func.sum(Receivable.valor), 2).label("valor_total"))
        .group_by(faixa_case)
        .order_by(faixa_case)
    ).all()
    return {"items": [{"faixa": faixa, "quantidade": quantidade, "valor_total": valor_total} for faixa, quantidade, valor_total in rows]}


@router.get(
    f"{PREFIX}/receivables/{{receivable_id}}",
    response_model=ReceivableResponse,
    tags=[TAG],
    operation_id="labs_group07_get_receivable",
    summary="Get one receivable by id",
    responses={404: {"description": "Receivable not found"}, 422: _RESPONSES_422},
)
async def get_receivable(
    receivable_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ReceivableResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return ReceivableResponse.model_validate(_receivable_or_404(db, receivable_id))


@router.get(
    f"{PREFIX}/receivables/{{receivable_id}}/collection-decision",
    response_model=CollectionDecisionResponse,
    tags=[TAG],
    operation_id="labs_group07_collection_decision",
    summary="Show which collection action applies and the history so far",
    responses={404: {"description": "Receivable not found"}, 422: _RESPONSES_422},
)
async def collection_decision(
    receivable_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CollectionDecisionResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    receivable = _receivable_or_404(db, receivable_id)
    config = _applicable_config(db, receivable)
    history = _history_for_receivable(db, receivable_id)
    return CollectionDecisionResponse(
        receivable=ReceivableResponse.model_validate(receivable),
        applicable_config=CollectionConfigResponse.model_validate(config) if config is not None else None,
        history=[CollectionHistoryResponse.model_validate(item) for item in history],
    )


@router.post(
    f"{PREFIX}/receivables/{{receivable_id}}/send-collection",
    response_model=CollectionHistoryResponse,
    tags=[TAG],
    operation_id="labs_group07_send_collection",
    summary="Send or register the applicable collection action with same-day idempotency",
    responses={404: {"description": "Receivable not found"}, 422: _RESPONSES_422},
)
async def send_collection(
    receivable_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CollectionHistoryResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    receivable = _receivable_or_404(db, receivable_id)
    history = _send_history(db, receivable, _applicable_config(db, receivable))
    db.commit()
    create_event(
        db,
        event_type="lab_group07_collection_sent",
        lab_group=x_lab_group,
        resource_type="lab_g07_receivable",
        resource_id=receivable.id_titulo,
        metadata={"group": "07", "history_id": history.id},
    )
    return CollectionHistoryResponse.model_validate(history)


@router.post(
    f"{PREFIX}/receivables/bulk-send",
    response_model=BulkSendResult,
    tags=[TAG],
    operation_id="labs_group07_bulk_send",
    summary="Process a bulk collection batch by aging bucket with partial failure reporting",
    responses={422: _RESPONSES_422},
)
async def bulk_send(
    payload: BulkSendRequest,
    scenario: Scenario = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> BulkSendResult:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    receivables = [item for item in db.execute(select(Receivable).order_by(Receivable.id_titulo.asc())).scalars().all() if faixa_label(item.dias_atraso) == payload.faixa][: payload.limit]
    outcomes: list[CollectionHistoryResponse] = []
    success = failed = ignored = 0
    for receivable in receivables:
        history = _send_history(db, receivable, _applicable_config(db, receivable))
        if history.resultado == "SUCESSO":
            success += 1
        elif history.resultado == "FALHA":
            failed += 1
        else:
            ignored += 1
        outcomes.append(CollectionHistoryResponse.model_validate(history))
    db.commit()
    create_event(
        db,
        event_type="lab_group07_bulk_collection_sent",
        lab_group=x_lab_group,
        resource_type="lab_g07_bulk",
        resource_id=payload.faixa,
        metadata={"group": "07", "processed": len(receivables)},
    )
    return BulkSendResult(processed=len(receivables), success=success, failed=failed, ignored=ignored, outcomes=outcomes)


@router.post(
    f"{PREFIX}/receivables/{{receivable_id}}/write-off",
    response_model=ReceivableResponse,
    tags=[TAG],
    operation_id="labs_group07_write_off",
    summary="Write off a receivable by moving it to CANCELADO",
    responses={404: {"description": "Receivable not found"}, 422: _RESPONSES_422},
)
async def write_off(
    receivable_id: str,
    payload: WriteOffRequest,
    scenario: Scenario = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ReceivableResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    receivable = _receivable_or_404(db, receivable_id)
    receivable.status = "CANCELADO"
    receivable.updated_at = LAB_NOW
    history = CollectionHistory(
        id=_next_history_id(db),
        id_titulo=receivable.id_titulo,
        config_id=None,
        acao="WRITE_OFF",
        canal="workflow",
        mensagem_enviada=payload.motivo,
        enviada_em=LAB_NOW,
        resultado="IGNORADO",
        respondedido=True,
        motivo=payload.motivo,
    )
    db.add(history)
    db.commit()
    create_event(
        db,
        event_type="lab_group07_receivable_written_off",
        lab_group=x_lab_group,
        resource_type="lab_g07_receivable",
        resource_id=receivable.id_titulo,
        metadata={"group": "07"},
    )
    return ReceivableResponse.model_validate(receivable)


@router.post(
    f"{PREFIX}/process-retry",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group07_process_retry",
    summary="Retry failed collection history rows idempotently",
    responses={422: _RESPONSES_422},
)
async def process_retry(
    scenario: Scenario = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    retry_rows = db.execute(select(CollectionHistory).where(CollectionHistory.resultado == "FALHA", CollectionHistory.respondedido.is_(False))).scalars().all()
    retried: list[CollectionHistoryResponse] = []
    for row in retry_rows:
        receivable = _receivable_or_404(db, row.id_titulo)
        config = db.get(CollectionConfig, row.config_id) if row.config_id else None
        row.respondedido = True
        history = _send_history(db, receivable, config)
        if history.id != row.id:
            retried.append(CollectionHistoryResponse.model_validate(history))
    db.commit()
    create_event(
        db,
        event_type="lab_group07_retry_processed",
        lab_group=x_lab_group,
        resource_type="lab_g07_retry",
        resource_id="retry",
        metadata={"group": "07", "processed": len(retried)},
    )
    return {"processed": len(retried), "items": [item.model_dump() for item in retried]}


@router.get(
    f"{PREFIX}/instructor/receivables/{{receivable_id}}",
    response_model=ReceivableInstructorResponse,
    tags=[TAG],
    operation_id="labs_group07_instructor_get_receivable",
    summary="Instructor only: get one receivable including the hidden send decision",
    responses={401: {"description": "Missing or invalid X-Instructor-Key"}, 403: {"description": "Instructor endpoints disabled on this environment"}, 404: {"description": "Receivable not found"}, 422: _RESPONSES_422},
)
async def instructor_get_receivable(
    receivable_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group07,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ReceivableInstructorResponse:
    await apply_scenario(scenario_or_422(scenario))
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    return ReceivableInstructorResponse.model_validate(_receivable_or_404(db, receivable_id))
