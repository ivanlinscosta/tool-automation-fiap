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
from ....labs.generators import LAB_NOW, LAB_TODAY
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group08_unlock import (
    ContractSummaryResponse,
    CreditCheck,
    CreditCheckResponse,
    CustomerContract,
    CustomerContractResponse,
    DecisionActor,
    Invoice,
    InvoiceResponse,
    UnlockDecision,
    UnlockDecisionResponse,
    UnlockHistory,
    UnlockHistoryResponse,
    UnlockRequest,
    UnlockRequestCreate,
    UnlockRequestInstructorResponse,
    UnlockRequestResponse,
    UnlockStatsResponse,
    PromiseCreate,
    expected_unlock_decision,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 08"
Group08 = Depends(require_group(8))

REQUEST_SORT_FIELDS = ("requested_at", "resolved_at", "status", "customer_id")
CONTRACT_SORT_FIELDS = ("customer_name", "contract_status", "monthly_value", "pending_invoices")
INVOICE_SORT_FIELDS = ("data_vencimento", "status", "valor")
CREDIT_SORT_FIELDS = ("data_consulta", "score", "resultado")
HISTORY_SORT_FIELDS = ("occurred_at", "acao", "status_novo")

_RESPONSES_422 = {
    "description": "Simulated validation error requested via ?scenario=validation_error",
    "content": {"application/json": {"example": {"detail": "Simulated validation error"}}},
}


def _contract_or_404(db: Session, customer_id: str) -> CustomerContract:
    contract = db.get(CustomerContract, customer_id)
    if contract is None:
        raise entity_not_found("CustomerContract", customer_id)
    return contract


def _request_or_404(db: Session, request_id: str) -> UnlockRequest:
    request = db.get(UnlockRequest, request_id)
    if request is None:
        raise entity_not_found("UnlockRequest", request_id)
    return request


def _decision_or_404(db: Session, decision_id: str) -> UnlockDecision:
    decision = db.get(UnlockDecision, decision_id)
    if decision is None:
        raise entity_not_found("UnlockDecision", decision_id)
    return decision


def _next_request_id(db: Session) -> str:
    highest = db.execute(select(UnlockRequest.request_id).order_by(UnlockRequest.request_id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "UR-000001"
    return f"UR-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _next_protocol(db: Session) -> str:
    highest = db.execute(select(UnlockRequest.protocol).order_by(UnlockRequest.protocol.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "PRT-00000001"
    return f"PRT-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:08d}"


def _next_history_id(db: Session) -> str:
    existing = [
        item
        for item in db.execute(select(UnlockHistory.history_id).where(UnlockHistory.history_id.like("UHA-%"))).scalars().all()
    ]
    highest = max((int(item.rsplit('-', maxsplit=1)[1]) for item in existing), default=0)
    pending = sum(1 for item in db.new if isinstance(item, UnlockHistory) and item.history_id.startswith("UHA-"))
    return f"UHA-{highest + pending + 1:06d}"


def _next_decision_id(db: Session) -> str:
    highest = db.execute(select(UnlockDecision.decision_id).order_by(UnlockDecision.decision_id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "DEC-000001"
    return f"DEC-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _latest_credit_check(db: Session, customer_id: str) -> CreditCheck | None:
    query = select(CreditCheck).where(CreditCheck.customer_id == customer_id).order_by(CreditCheck.data_consulta.desc(), CreditCheck.check_id.desc()).limit(1)
    return db.execute(query).scalar_one_or_none()


def _request_history(db: Session, request_id: str) -> list[UnlockHistory]:
    query = select(UnlockHistory).where(UnlockHistory.request_id == request_id).order_by(UnlockHistory.occurred_at.asc(), UnlockHistory.history_id.asc())
    return list(db.execute(query).scalars().all())


def _build_credit_check(db: Session, request: UnlockRequest) -> CreditCheck:
    existing_history = db.execute(
        select(UnlockHistory).where(UnlockHistory.request_id == request.request_id, UnlockHistory.acao == "CREDIT_CHECK")
    ).scalar_one_or_none()
    existing_check = _latest_credit_check(db, request.customer_id)
    if existing_history is not None and existing_check is not None:
        return existing_check
    base = int(request.customer_id.rsplit('-', maxsplit=1)[1])
    score = 320 + (base * 37) % 620
    limite_credito = round(500.0 + (base % 35) * 220.0, 2)
    contract = _contract_or_404(db, request.customer_id)
    usado = round(min(limite_credito, contract.monthly_value * max(1, contract.pending_invoices)), 2)
    disponivel = round(max(0.0, limite_credito - usado), 2)
    resultado = "APROVADO" if score >= 700 else ("ANALISE_MANUAL" if score >= 450 else "REJEITADO")
    credit_check = CreditCheck(
        check_id=f"CHK-{base:06d}",
        customer_id=request.customer_id,
        score=score,
        limite_credito=limite_credito,
        usado=usado,
        disponivel=disponivel,
        data_consulta=LAB_NOW,
        resultado=resultado,
    )
    db.merge(credit_check)
    history = UnlockHistory(
        history_id=_next_history_id(db),
        customer_id=request.customer_id,
        request_id=request.request_id,
        acao="CREDIT_CHECK",
        status_anterior=request.status,
        status_novo="EM_ANALISE",
        executed_by="credit.bot",
        occurred_at=LAB_NOW,
    )
    request.status = "EM_ANALISE"
    db.add(history)
    return credit_check


@router.get(
    f"{PREFIX}/unlock-requests",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group08_list_unlock_requests",
    summary="List unlock requests",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_unlock_requests(
    scenario: Scenario = None,
    group: LabGroup = Group08,
    status_filter: str | None = Query(default=None, alias="status"),
    customer_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(REQUEST_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(UnlockRequest)
    if status_filter:
        query = query.where(UnlockRequest.status == status_filter)
    if customer_id:
        query = query.where(UnlockRequest.customer_id == customer_id)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(UnlockRequest.protocol).like(pattern),
                func.lower(UnlockRequest.motivo).like(pattern),
                func.lower(UnlockRequest.customer_id).like(pattern),
            )
        )
    query = apply_sort(query, UnlockRequest, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: UnlockRequestResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/unlock-requests/{{request_id}}",
    response_model=UnlockRequestResponse,
    tags=[TAG],
    operation_id="labs_group08_get_unlock_request",
    summary="Get one unlock request by id",
    responses={404: {"description": "Unlock request not found"}, 422: _RESPONSES_422},
)
async def get_unlock_request(
    request_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> UnlockRequestResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return UnlockRequestResponse.model_validate(_request_or_404(db, request_id))


@router.post(
    f"{PREFIX}/unlock-requests",
    response_model=UnlockRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group08_create_unlock_request",
    summary="Register an unlock-on-trust request",
    responses={404: {"description": "Customer contract not found"}, 422: _RESPONSES_422},
)
async def create_unlock_request(
    payload: UnlockRequestCreate,
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> UnlockRequestResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    contract = _contract_or_404(db, payload.customer_id)
    score = 320 + (int(contract.customer_id.rsplit('-', maxsplit=1)[1]) * 37) % 620
    expected, _ = expected_unlock_decision(
        contract_status=contract.contract_status,
        pending_invoices=contract.pending_invoices,
        score=score,
        promise_date=None,
        today=LAB_TODAY,
    )
    request = UnlockRequest(
        request_id=_next_request_id(db),
        customer_id=contract.customer_id,
        protocol=_next_protocol(db),
        motivo=payload.motivo,
        status="RECEBIDO",
        requested_at=LAB_NOW,
        resolved_at=None,
        promessa_pagamento_data=None,
        decision_id=None,
        decisao_esperada=expected,
    )
    history = UnlockHistory(
        history_id=_next_history_id(db),
        customer_id=contract.customer_id,
        request_id=request.request_id,
        acao="CRIAR",
        status_anterior=None,
        status_novo="RECEBIDO",
        executed_by="api.user",
        occurred_at=LAB_NOW,
    )
    db.add(request)
    db.add(history)
    db.commit()
    create_event(
        db,
        event_type="lab_group08_unlock_request_created",
        lab_group=x_lab_group,
        resource_type="lab_g08_unlock_request",
        resource_id=request.request_id,
        metadata={"group": "08", "customer_id": contract.customer_id},
    )
    return UnlockRequestResponse.model_validate(request)


@router.post(
    f"{PREFIX}/unlock-requests/{{request_id}}/credit-check",
    response_model=CreditCheckResponse,
    tags=[TAG],
    operation_id="labs_group08_credit_check",
    summary="Run a deterministic mock credit consultation for the request",
    responses={404: {"description": "Unlock request not found"}, 422: _RESPONSES_422},
)
async def credit_check(
    request_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CreditCheckResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    request = _request_or_404(db, request_id)
    credit = _build_credit_check(db, request)
    db.commit()
    create_event(
        db,
        event_type="lab_group08_credit_checked",
        lab_group=x_lab_group,
        resource_type="lab_g08_unlock_request",
        resource_id=request.request_id,
        metadata={"group": "08", "check_id": credit.check_id},
    )
    return CreditCheckResponse.model_validate(credit)


@router.post(
    f"{PREFIX}/unlock-requests/{{request_id}}/promise",
    response_model=UnlockRequestResponse,
    tags=[TAG],
    operation_id="labs_group08_register_promise",
    summary="Register a promise-to-pay date for an unlock request",
    responses={404: {"description": "Unlock request not found"}, 422: _RESPONSES_422},
)
async def register_promise(
    request_id: str,
    payload: PromiseCreate,
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> UnlockRequestResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if payload.promessa_pagamento_data < LAB_TODAY:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A promessa de pagamento nao pode estar no passado")
    request = _request_or_404(db, request_id)
    previous_status = request.status
    request.promessa_pagamento_data = payload.promessa_pagamento_data
    request.status = "AGUARDANDO_PROMESSA"
    history = UnlockHistory(
        history_id=_next_history_id(db),
        customer_id=request.customer_id,
        request_id=request.request_id,
        acao="PROMESSA",
        status_anterior=previous_status,
        status_novo=request.status,
        executed_by="api.user",
        occurred_at=LAB_NOW,
    )
    db.add(history)
    db.commit()
    create_event(
        db,
        event_type="lab_group08_promise_registered",
        lab_group=x_lab_group,
        resource_type="lab_g08_unlock_request",
        resource_id=request.request_id,
        metadata={"group": "08", "promise_date": payload.promessa_pagamento_data.isoformat()},
    )
    return UnlockRequestResponse.model_validate(request)


@router.post(
    f"{PREFIX}/unlock-requests/{{request_id}}/decide",
    response_model=UnlockDecisionResponse,
    tags=[TAG],
    operation_id="labs_group08_decide_unlock_request",
    summary="Apply the deterministic unlock decision rule and persist the decision",
    responses={404: {"description": "Unlock request not found"}, 422: _RESPONSES_422},
)
async def decide_unlock_request(
    request_id: str,
    payload: DecisionActor | None = None,
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> UnlockDecisionResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    request = _request_or_404(db, request_id)
    if request.decision_id:
        return UnlockDecisionResponse.model_validate(_decision_or_404(db, request.decision_id))
    actor = payload.executed_by if payload is not None else "analista.lab"
    credit = _latest_credit_check(db, request.customer_id)
    if credit is None:
        credit = _build_credit_check(db, request)
    contract = _contract_or_404(db, request.customer_id)
    decision_name, justification = expected_unlock_decision(
        contract_status=contract.contract_status,
        pending_invoices=contract.pending_invoices,
        score=credit.score,
        promise_date=request.promessa_pagamento_data,
        today=LAB_TODAY,
    )
    decision = UnlockDecision(
        decision_id=_next_decision_id(db),
        request_id=request.request_id,
        decision=decision_name,
        justification=justification,
        decided_at=LAB_NOW,
        credit_check_id=credit.check_id,
        score_usado=credit.score,
    )
    previous_status = request.status
    request.decision_id = decision.decision_id
    request.resolved_at = LAB_NOW
    request.status = "APROVADO" if decision_name == "LIBERADO" else "REJEITADO"
    history = UnlockHistory(
        history_id=_next_history_id(db),
        customer_id=request.customer_id,
        request_id=request.request_id,
        acao="DECIDIR",
        status_anterior=previous_status,
        status_novo=request.status,
        executed_by=actor,
        occurred_at=LAB_NOW,
    )
    db.add(decision)
    db.add(history)
    db.commit()
    create_event(
        db,
        event_type="lab_group08_unlock_decided",
        lab_group=x_lab_group,
        resource_type="lab_g08_unlock_request",
        resource_id=request.request_id,
        metadata={"group": "08", "decision": decision.decision},
    )
    return UnlockDecisionResponse.model_validate(decision)


@router.post(
    f"{PREFIX}/unlock-requests/{{request_id}}/provision",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group08_provision_unlock",
    summary="Execute the mock provisioning step when the request was released",
    responses={404: {"description": "Unlock request not found"}, 409: {"description": "Provisioning is not allowed for this request"}, 422: _RESPONSES_422},
)
async def provision_unlock(
    request_id: str,
    payload: DecisionActor | None = None,
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    request = _request_or_404(db, request_id)
    if not request.decision_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A requisicao ainda nao possui decisao")
    decision = _decision_or_404(db, request.decision_id)
    if decision.decision != "LIBERADO":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provisionamento permitido apenas para decisoes LIBERADO")
    actor = payload.executed_by if payload is not None else "provision.bot"
    existing = db.execute(select(UnlockHistory).where(UnlockHistory.request_id == request.request_id, UnlockHistory.acao == "PROVISION")).scalar_one_or_none()
    if existing is None:
        history = UnlockHistory(
            history_id=_next_history_id(db),
            customer_id=request.customer_id,
            request_id=request.request_id,
            acao="PROVISION",
            status_anterior=request.status,
            status_novo=request.status,
            executed_by=actor,
            occurred_at=LAB_NOW,
        )
        db.add(history)
        db.commit()
    create_event(
        db,
        event_type="lab_group08_unlock_provisioned",
        lab_group=x_lab_group,
        resource_type="lab_g08_unlock_request",
        resource_id=request.request_id,
        metadata={"group": "08"},
    )
    return {"request_id": request.request_id, "decision": decision.decision, "provisioned": True}


@router.get(
    f"{PREFIX}/contracts",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group08_list_contracts",
    summary="List customer contracts",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_contracts(
    scenario: Scenario = None,
    group: LabGroup = Group08,
    contract_status: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(CONTRACT_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(CustomerContract)
    if contract_status:
        query = query.where(CustomerContract.contract_status == contract_status)
    query = apply_sort(query, CustomerContract, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: CustomerContractResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/contracts/{{customer_id}}/summary",
    response_model=ContractSummaryResponse,
    tags=[TAG],
    operation_id="labs_group08_contract_summary",
    summary="Return the contract, invoices and latest credit check rollup",
    responses={404: {"description": "Customer contract not found"}, 422: _RESPONSES_422},
)
async def contract_summary(
    customer_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ContractSummaryResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    contract = _contract_or_404(db, customer_id)
    invoices = db.execute(select(Invoice).where(Invoice.customer_id == customer_id).order_by(Invoice.data_vencimento.desc())).scalars().all()
    credit = _latest_credit_check(db, customer_id)
    return ContractSummaryResponse(
        contract=CustomerContractResponse.model_validate(contract),
        invoices=[InvoiceResponse.model_validate(item) for item in invoices],
        latest_credit_check=CreditCheckResponse.model_validate(credit) if credit is not None else None,
    )


@router.get(
    f"{PREFIX}/invoices",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group08_list_invoices",
    summary="List invoices linked to customer contracts",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_invoices(
    scenario: Scenario = None,
    group: LabGroup = Group08,
    customer_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(INVOICE_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Invoice)
    if customer_id:
        query = query.where(Invoice.customer_id == customer_id)
    if status_filter:
        query = query.where(Invoice.status == status_filter)
    query = apply_sort(query, Invoice, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: InvoiceResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/credit-checks",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group08_list_credit_checks",
    summary="List mock credit checks",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_credit_checks(
    scenario: Scenario = None,
    group: LabGroup = Group08,
    customer_id: str | None = Query(default=None),
    resultado: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(CREDIT_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(CreditCheck)
    if customer_id:
        query = query.where(CreditCheck.customer_id == customer_id)
    if resultado:
        query = query.where(CreditCheck.resultado == resultado)
    query = apply_sort(query, CreditCheck, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: CreditCheckResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/unlock-history",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group08_list_history",
    summary="List unlock workflow history",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_history(
    scenario: Scenario = None,
    group: LabGroup = Group08,
    request_id: str | None = Query(default=None),
    acao: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(HISTORY_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(UnlockHistory)
    if request_id:
        query = query.where(UnlockHistory.request_id == request_id)
    if acao:
        query = query.where(UnlockHistory.acao == acao)
    query = apply_sort(query, UnlockHistory, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: UnlockHistoryResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/unlock-stats",
    response_model=UnlockStatsResponse,
    tags=[TAG],
    operation_id="labs_group08_stats",
    summary="Aggregate unlock requests by status and unlock decisions by type",
    responses={422: _RESPONSES_422},
)
async def unlock_stats(
    scenario: Scenario = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> UnlockStatsResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    requests_by_status = {key: value for key, value in db.execute(select(UnlockRequest.status, func.count()).group_by(UnlockRequest.status)).all()}
    decisions_by_type = {key: value for key, value in db.execute(select(UnlockDecision.decision, func.count()).group_by(UnlockDecision.decision)).all()}
    return UnlockStatsResponse(requests_by_status=requests_by_status, decisions_by_type=decisions_by_type)


@router.get(
    f"{PREFIX}/instructor/unlock-requests/{{request_id}}",
    response_model=UnlockRequestInstructorResponse,
    tags=[TAG],
    operation_id="labs_group08_instructor_get_unlock_request",
    summary="Instructor only: get one unlock request including the hidden expected decision",
    responses={401: {"description": "Missing or invalid X-Instructor-Key"}, 403: {"description": "Instructor endpoints disabled on this environment"}, 404: {"description": "Unlock request not found"}, 422: _RESPONSES_422},
)
async def instructor_get_unlock_request(
    request_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group08,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> UnlockRequestInstructorResponse:
    await apply_scenario(scenario_or_422(scenario))
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    return UnlockRequestInstructorResponse.model_validate(_request_or_404(db, request_id))
