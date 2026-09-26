import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.corpus_group03 import (
    GROUP03_LOAD_LOG_ERROR,
    GROUP03_LOAD_LOG_WARN,
    GROUP03_VALIDATION_CNPJ,
    GROUP03_VALIDATION_OK,
    GROUP03_VALIDATION_PRODUCT,
    GROUP03_VALIDATION_VALUE,
)
from ....labs.deps import (
    LABS_GROUP_PATH,
    LabGroupHeader,
    Scenario,
    entity_not_found,
    require_group,
    scenario_or_422,
)
from ....labs.generators import LAB_NOW, is_valid_cnpj
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group03_bitrix import (
    AuthorizedRequester,
    AuthorizedRequesterResponse,
    CrmContact,
    CrmContactResponse,
    CrmDeal,
    CrmDealResponse,
    Load,
    LoadCreate,
    LoadCreateRejected,
    LoadLog,
    LoadLogResponse,
    LoadResponse,
    LoadSyncResponse,
    OPPORTUNITY_STAGES,
    Opportunity,
    OpportunityResponse,
    OpportunityValidateRequest,
    OpportunityValidation,
    OpportunityValidationResponse,
    ProductPipelineMap,
    ProductPipelineMapResponse,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 03"
Group03 = Depends(require_group(3))
IdempotencyKey = Header(
    default=None,
    alias="Idempotency-Key",
    description=(
        "Stable client key used to replay a load without duplicating CRM deals."
    ),
)
OPPORTUNITY_SORT_FIELDS = (
    "opportunity_id",
    "load_id",
    "produto",
    "stage",
    "valor",
    "created_at",
    "updated_at",
)
LOAD_SORT_FIELDS = (
    "carga_id",
    "requester_email",
    "status",
    "opportunities_count",
    "deals_created",
    "created_at",
    "updated_at",
)
LOG_SORT_FIELDS = ("log_id", "carga_id", "level", "created_at")
REQUESTER_SORT_FIELDS = ("requester_id", "nome", "email", "area", "ativo")
CONTACT_SORT_FIELDS = (
    "contact_id",
    "nome",
    "email",
    "empresa",
    "created_at",
    "updated_at",
)
DEAL_SORT_FIELDS = (
    "deal_id",
    "contact_id",
    "load_id",
    "pipeline_codigo",
    "stage",
    "valor",
    "created_at",
    "updated_at",
)
MAP_SORT_FIELDS = ("map_id", "produto", "pipeline_codigo", "etapa_padrao", "ativo")

_GROUP03_422 = {
    "description": (
        "Simulated validation error requested via ?scenario=validation_error"
    ),
    "content": {
        "application/json": {"example": {"detail": "Simulated validation error"}}
    },
}


def _opportunity_or_404(db: Session, opportunity_id: str) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise entity_not_found("Opportunity", opportunity_id)
    return opportunity


def _load_or_404(db: Session, load_id: str) -> Load:
    load = db.get(Load, load_id)
    if load is None:
        raise entity_not_found("Load", load_id)
    return load


def _next_id(db: Session, model: type, field, prefix: str, width: int) -> str:
    highest = db.execute(
        select(field).order_by(field.desc()).limit(1)
    ).scalar_one_or_none()
    if highest is None:
        return f"{prefix}-{'1'.zfill(width)}"
    return f"{prefix}-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:0{width}d}"


def _payload_hash(payload: LoadCreate) -> str:
    return hashlib.sha1(
        f"{payload.requester_email}\n{payload.lista_free_text.strip()}".encode("utf-8")
    ).hexdigest()


def _bitrix_id(opportunity_id: str) -> str:
    digest = hashlib.sha1(opportunity_id.encode("utf-8")).hexdigest()[:12].upper()
    return f"BTRX-{digest}"


def _parse_stage(value: str) -> str:
    cleaned = value.strip().lower()
    return cleaned if cleaned in OPPORTUNITY_STAGES else "novo"


def _validation_reason(cnpj_ok: bool, value_ok: bool, mapped_ok: bool) -> str:
    if not cnpj_ok:
        return GROUP03_VALIDATION_CNPJ[0]
    if not value_ok:
        return GROUP03_VALIDATION_VALUE[0]
    if not mapped_ok:
        return GROUP03_VALIDATION_PRODUCT[0]
    return GROUP03_VALIDATION_OK[0]


def _ensure_requester(db: Session, requester_email: str) -> AuthorizedRequester | None:
    return db.execute(
        select(AuthorizedRequester).where(AuthorizedRequester.email == requester_email)
    ).scalar_one_or_none()


def _pipeline_map(db: Session, produto: str) -> ProductPipelineMap | None:
    return db.execute(
        select(ProductPipelineMap).where(
            ProductPipelineMap.produto == produto, ProductPipelineMap.ativo.is_(True)
        )
    ).scalar_one_or_none()


def _existing_contact(db: Session, email: str) -> CrmContact | None:
    return db.execute(
        select(CrmContact).where(CrmContact.email == email)
    ).scalar_one_or_none()


@router.get(
    f"{PREFIX}/opportunities",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group03_list_opportunities",
    summary="List opportunities derived from RevOps loads",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP03_422},
)
async def list_opportunities(
    scenario: Scenario = None,
    group: LabGroup = Group03,
    stage: str | None = Query(default=None, description="Filter by opportunity stage."),
    carga_id: str | None = Query(default=None, description="Filter by parent load id."),
    produto: str | None = Query(default=None, description="Filter by product name."),
    search: str | None = Query(
        default=None, description="Case-insensitive search on empresa, contato or cnpj."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(OPPORTUNITY_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Opportunity)
    if stage:
        query = query.where(Opportunity.stage == stage)
    if carga_id:
        query = query.where(Opportunity.load_id == carga_id)
    if produto:
        query = query.where(Opportunity.produto == produto)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Opportunity.empresa).like(pattern),
                func.lower(Opportunity.contato_nome).like(pattern),
                func.lower(Opportunity.contato_email).like(pattern),
                func.lower(Opportunity.cnpj).like(pattern),
            )
        )
    query = (
        apply_sort(query, Opportunity, sort, order)
        if sort
        else query.order_by(Opportunity.opportunity_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: OpportunityResponse.model_validate(item).model_dump(),
    )


@router.post(
    f"{PREFIX}/loads",
    response_model=LoadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group03_create_load",
    summary="Parse a free-text RevOps list into opportunities, contacts and CRM deals",
    responses={
        403: {"description": "Unauthorized requester"},
        409: {"description": "Idempotency conflict"},
        422: _GROUP03_422,
    },
)
async def create_load(
    payload: LoadCreate,
    scenario: Scenario = None,
    group: LabGroup = Group03,
    idempotency_key: str | None = IdempotencyKey,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LoadResponse | JSONResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    payload_digest = _payload_hash(payload)
    existing = None
    if idempotency_key:
        existing = db.execute(
            select(Load).where(Load.chave_idempotencia == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            if existing.payload_hash != payload_digest:
                db.add(
                    LoadLog(
                        log_id=_next_id(db, LoadLog, LoadLog.log_id, "LOG", 6),
                        carga_id=existing.carga_id,
                        level="ERROR",
                        message=GROUP03_LOAD_LOG_ERROR[1],
                        created_at=LAB_NOW,
                    )
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key replay with different payload",
                )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=LoadResponse.model_validate(existing).model_dump(mode="json"),
            )

    requester = _ensure_requester(db, payload.requester_email)
    if requester is None or not requester.ativo:
        load_id = _next_id(db, Load, Load.carga_id, "LOAD", 4)
        rejected = Load(
            carga_id=load_id,
            requester_email=payload.requester_email,
            lista_free_text=payload.lista_free_text.strip(),
            chave_idempotencia=idempotency_key,
            payload_hash=payload_digest,
            status="REJEITADO",
            opportunities_count=0,
            deals_created=0,
            created_at=LAB_NOW,
            updated_at=LAB_NOW,
        )
        db.add(rejected)
        db.flush()
        db.add(
            LoadLog(
                log_id=_next_id(db, LoadLog, LoadLog.log_id, "LOG", 6),
                carga_id=rejected.carga_id,
                level="ERROR",
                message=GROUP03_LOAD_LOG_ERROR[0],
                created_at=LAB_NOW,
            )
        )
        db.commit()
        create_event(
            db,
            event_type="lab_group03_load_rejected",
            lab_group=x_lab_group,
            resource_type="lab_load",
            resource_id=rejected.carga_id,
            metadata={"group": "03", "requester_email": payload.requester_email},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=LoadCreateRejected(
                message="Requester is not authorized", carga_id=rejected.carga_id
            ).model_dump(),
        )

    created_at = LAB_NOW
    load = Load(
        carga_id=_next_id(db, Load, Load.carga_id, "LOAD", 4),
        requester_email=payload.requester_email,
        lista_free_text=payload.lista_free_text.strip(),
        chave_idempotencia=idempotency_key,
        payload_hash=payload_digest,
        status="PROCESSADO",
        opportunities_count=0,
        deals_created=0,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(load)
    db.flush()

    contact_cache: dict[str, CrmContact] = {}
    deals_created = 0
    invalid_lines = 0
    lines = [
        line.strip() for line in payload.lista_free_text.splitlines() if line.strip()
    ]
    for line_number, line in enumerate(lines, start=1):
        parts = [part.strip() for part in line.split("|")]
        (
            empresa,
            document,
            produto,
            valor_raw,
            contato_nome,
            contato_email,
            stage_raw,
        ) = (parts + [""] * 7)[:7]
        stage = _parse_stage(stage_raw)
        try:
            valor = float(valor_raw.replace(",", "."))
        except ValueError:
            valor = 0.0
        opportunity_id = _next_id(db, Opportunity, Opportunity.opportunity_id, "OPP", 6)
        opportunity = Opportunity(
            opportunity_id=opportunity_id,
            load_id=load.carga_id,
            line_number=line_number,
            empresa=empresa or f"Empresa {line_number}",
            cnpj=document or "00.000.000/0000-00",
            produto=produto or "Produto Sem Mapa",
            valor=valor,
            contato_nome=contato_nome or "Contato nao informado",
            contato_email=contato_email or f"contato.{line_number:03d}@example.com",
            stage=stage,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(opportunity)
        db.flush()

        cnpj_ok = is_valid_cnpj(opportunity.cnpj)
        value_ok = opportunity.valor > 0
        mapped = _pipeline_map(db, opportunity.produto)
        mapped_ok = mapped is not None
        validation = OpportunityValidation(
            validation_id=_next_id(
                db, OpportunityValidation, OpportunityValidation.validation_id, "VAL", 6
            ),
            opportunity_id=opportunity.opportunity_id,
            cnpj_valido=cnpj_ok,
            valor_valido=value_ok,
            produto_mapeado=mapped_ok,
            motivo=_validation_reason(cnpj_ok, value_ok, mapped_ok),
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(validation)
        if not (cnpj_ok and value_ok and mapped_ok):
            invalid_lines += 1

        contact = contact_cache.get(opportunity.contato_email) or _existing_contact(
            db, opportunity.contato_email
        )
        if contact is None:
            contact = CrmContact(
                contact_id=_next_id(db, CrmContact, CrmContact.contact_id, "CTT", 6),
                nome=opportunity.contato_nome,
                email=opportunity.contato_email,
                empresa=opportunity.empresa,
                cnpj=opportunity.cnpj,
                owner_user_id=None,
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(contact)
            db.flush()
        contact_cache[opportunity.contato_email] = contact

        if cnpj_ok and value_ok and mapped_ok and mapped is not None:
            db.add(
                CrmDeal(
                    deal_id=_next_id(db, CrmDeal, CrmDeal.deal_id, "DEAL", 6),
                    contact_id=contact.contact_id,
                    opportunity_id=opportunity.opportunity_id,
                    load_id=load.carga_id,
                    pipeline_codigo=mapped.pipeline_codigo,
                    stage=opportunity.stage,
                    valor=opportunity.valor,
                    bitrix_id=_bitrix_id(opportunity.opportunity_id),
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            deals_created += 1

    load.opportunities_count = len(lines)
    load.deals_created = deals_created
    load.status = "PARCIAL" if invalid_lines else "PROCESSADO"
    load.updated_at = created_at

    db.add(
        LoadLog(
            log_id=_next_id(db, LoadLog, LoadLog.log_id, "LOG", 6),
            carga_id=load.carga_id,
            level="WARN" if invalid_lines else "INFO",
            message=GROUP03_LOAD_LOG_WARN[0]
            if invalid_lines
            else GROUP03_VALIDATION_OK[1],
            created_at=created_at,
        )
    )
    db.commit()
    create_event(
        db,
        event_type="lab_group03_load_created",
        lab_group=x_lab_group,
        resource_type="lab_load",
        resource_id=load.carga_id,
        metadata={
            "group": "03",
            "status": load.status,
            "deals_created": load.deals_created,
        },
    )
    return LoadResponse.model_validate(load)


@router.get(
    f"{PREFIX}/loads",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group03_list_loads",
    summary="List RevOps loads with status and idempotency metadata",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP03_422},
)
async def list_loads(
    scenario: Scenario = None,
    group: LabGroup = Group03,
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by load status."
    ),
    requester_email: str | None = Query(
        default=None, description="Filter by requester email."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(LOAD_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Load)
    if status_filter:
        query = query.where(Load.status == status_filter)
    if requester_email:
        query = query.where(Load.requester_email == requester_email)
    query = (
        apply_sort(query, Load, sort, order)
        if sort
        else query.order_by(Load.carga_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: LoadResponse.model_validate(item).model_dump(),
    )


@router.get(
    f"{PREFIX}/loads/{{load_id}}/crm-sync",
    response_model=LoadSyncResponse,
    tags=[TAG],
    operation_id="labs_group03_get_crm_sync",
    summary="Inspect the CRM deals created for one RevOps load",
    responses={404: {"description": "Load not found"}, 422: _GROUP03_422},
)
async def get_crm_sync(
    load_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group03,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LoadSyncResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    load = _load_or_404(db, load_id)
    deals = list(
        db.execute(
            select(CrmDeal)
            .where(CrmDeal.load_id == load_id)
            .order_by(CrmDeal.deal_id.asc())
        )
        .scalars()
        .all()
    )
    return LoadSyncResponse(
        carga_id=load.carga_id,
        status=load.status,
        deals_created=load.deals_created,
        deals=[CrmDealResponse.model_validate(item) for item in deals],
    )


@router.get(
    f"{PREFIX}/loads/{{load_id}}",
    response_model=LoadResponse,
    tags=[TAG],
    operation_id="labs_group03_get_load",
    summary="Get one RevOps load by id",
    responses={404: {"description": "Load not found"}, 422: _GROUP03_422},
)
async def get_load(
    load_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group03,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> LoadResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return LoadResponse.model_validate(_load_or_404(db, load_id))


@router.post(
    f"{PREFIX}/opportunities/{{opportunity_id}}/validate",
    response_model=OpportunityValidationResponse,
    tags=[TAG],
    operation_id="labs_group03_validate_opportunity",
    summary="Re-run deterministic validation for one opportunity",
    responses={404: {"description": "Opportunity not found"}, 422: _GROUP03_422},
)
async def validate_opportunity(
    opportunity_id: str,
    payload: OpportunityValidateRequest,
    scenario: Scenario = None,
    group: LabGroup = Group03,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> OpportunityValidationResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, payload)
    opportunity = _opportunity_or_404(db, opportunity_id)
    validation = db.execute(
        select(OpportunityValidation).where(
            OpportunityValidation.opportunity_id == opportunity.opportunity_id
        )
    ).scalar_one_or_none()
    if validation is None:
        raise entity_not_found("OpportunityValidation", opportunity.opportunity_id)
    cnpj_ok = is_valid_cnpj(opportunity.cnpj)
    value_ok = opportunity.valor > 0
    mapped_ok = _pipeline_map(db, opportunity.produto) is not None
    validation.cnpj_valido = cnpj_ok
    validation.valor_valido = value_ok
    validation.produto_mapeado = mapped_ok
    validation.motivo = _validation_reason(cnpj_ok, value_ok, mapped_ok)
    validation.updated_at = LAB_NOW
    db.commit()
    create_event(
        db,
        event_type="lab_group03_opportunity_validated",
        lab_group=x_lab_group,
        resource_type="lab_opportunity",
        resource_id=opportunity.opportunity_id,
        metadata={"group": "03", "load_id": opportunity.load_id},
    )
    return OpportunityValidationResponse.model_validate(validation)


@router.get(
    f"{PREFIX}/opportunities/{{opportunity_id}}",
    response_model=OpportunityResponse,
    tags=[TAG],
    operation_id="labs_group03_get_opportunity",
    summary="Get one opportunity by id",
    responses={404: {"description": "Opportunity not found"}, 422: _GROUP03_422},
)
async def get_opportunity(
    opportunity_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group03,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> OpportunityResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return OpportunityResponse.model_validate(_opportunity_or_404(db, opportunity_id))


@router.get(
    f"{PREFIX}/load-logs",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group03_list_load_logs",
    summary="List processing logs emitted by RevOps loads",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP03_422},
)
async def list_load_logs(
    scenario: Scenario = None,
    group: LabGroup = Group03,
    carga_id: str | None = Query(default=None, description="Filter by load id."),
    level: str | None = Query(
        default=None, description="Filter by INFO, WARN or ERROR."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(LOG_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(LoadLog)
    if carga_id:
        query = query.where(LoadLog.carga_id == carga_id)
    if level:
        query = query.where(LoadLog.level == level)
    query = (
        apply_sort(query, LoadLog, sort, order)
        if sort
        else query.order_by(LoadLog.log_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: LoadLogResponse.model_validate(item).model_dump(),
    )


@router.get(
    f"{PREFIX}/authorized-requesters",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group03_list_authorized_requesters",
    summary="List requesters allowed to create RevOps loads",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP03_422},
)
async def list_authorized_requesters(
    scenario: Scenario = None,
    group: LabGroup = Group03,
    active_only: bool = Query(
        default=False, description="Return only active requesters when true."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(REQUESTER_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(AuthorizedRequester)
    if active_only:
        query = query.where(AuthorizedRequester.ativo.is_(True))
    query = (
        apply_sort(query, AuthorizedRequester, sort, order)
        if sort
        else query.order_by(AuthorizedRequester.requester_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: AuthorizedRequesterResponse.model_validate(
            item
        ).model_dump(),
    )


@router.get(
    f"{PREFIX}/crm-contacts",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group03_list_crm_contacts",
    summary="List CRM contacts created from RevOps loads",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP03_422},
)
async def list_crm_contacts(
    scenario: Scenario = None,
    group: LabGroup = Group03,
    search: str | None = Query(
        default=None, description="Case-insensitive search on nome, empresa or email."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(CONTACT_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(CrmContact)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(CrmContact.nome).like(pattern),
                func.lower(CrmContact.empresa).like(pattern),
                func.lower(CrmContact.email).like(pattern),
            )
        )
    query = (
        apply_sort(query, CrmContact, sort, order)
        if sort
        else query.order_by(CrmContact.contact_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: CrmContactResponse.model_validate(item).model_dump(),
    )


@router.get(
    f"{PREFIX}/crm-deals",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group03_list_crm_deals",
    summary="List CRM deals created from valid opportunities",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP03_422},
)
async def list_crm_deals(
    scenario: Scenario = None,
    group: LabGroup = Group03,
    carga_id: str | None = Query(
        default=None, description="Filter by originating load id."
    ),
    pipeline_codigo: str | None = Query(
        default=None, description="Filter by pipeline code."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(DEAL_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(CrmDeal)
    if carga_id:
        query = query.where(CrmDeal.load_id == carga_id)
    if pipeline_codigo:
        query = query.where(CrmDeal.pipeline_codigo == pipeline_codigo)
    query = (
        apply_sort(query, CrmDeal, sort, order)
        if sort
        else query.order_by(CrmDeal.deal_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: CrmDealResponse.model_validate(item).model_dump(),
    )


@router.get(
    f"{PREFIX}/pipeline-maps",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group03_list_pipeline_maps",
    summary="List product-to-pipeline mappings used during CRM sync",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP03_422},
)
async def list_pipeline_maps(
    scenario: Scenario = None,
    group: LabGroup = Group03,
    active_only: bool = Query(
        default=False, description="Return only active pipeline mappings when true."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(MAP_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(ProductPipelineMap)
    if active_only:
        query = query.where(ProductPipelineMap.ativo.is_(True))
    query = (
        apply_sort(query, ProductPipelineMap, sort, order)
        if sort
        else query.order_by(ProductPipelineMap.map_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: ProductPipelineMapResponse.model_validate(
            item
        ).model_dump(),
    )
